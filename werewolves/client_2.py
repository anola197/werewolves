import threading
import sys
import select
from mpi4py import MPI

comm = MPI.COMM_WORLD

# Shared variable to control the threads' lifecycle
running = True

def send_messages(comm_mod):
    """Thread function to handle sending messages based on user input."""
    global running
    print("You can start typing your messages:")
    try:
        while running:
            # Non-blocking input
            ready, _, _ = select.select([sys.stdin], [], [], 1)  # Timeout adjusted to 1 second for responsiveness
            if ready:
                user_input = sys.stdin.readline().strip()
                if user_input.lower() == "exit":
                    print("Stopping message sending.")
                    running = False  # Update the flag to stop other operations
                else:
                    comm_mod.send(user_input, dest=0, tag=102)
    except KeyboardInterrupt:
        print("Sending interrupted by user.")
        running = False

def main():
    global running
    with open('port_name.txt', 'r') as file:
        port_name = file.readline().strip()

    server_comm = comm.Connect(port_name)
    print("Connected to server")
    sys.stdout.flush()

    sender_thread = threading.Thread(target=send_messages, args=(server_comm,))
    sender_thread.daemon = True
    sender_thread.start()

    try:
        while running:
            message = server_comm.recv(source=0)
            print(f"{message}")
            sys.stdout.flush()
            if message == "close":
                #print("Connection closed by server.")
                running = False 
    except Exception as e:
        print(f"Error during receiving: {e}")
        running = False
    finally:
        sender_thread.join()  # Now we're sure the thread is ready to join
        server_comm.Disconnect()
        MPI.Finalize()

if __name__ == '__main__':
    main()
