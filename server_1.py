from mpi4py import MPI
import time
import sys
import random

comm = MPI.COMM_WORLD
rank = comm.Get_rank()
conns = {}
winner = 'No winner'
wolves = []
witch =[]
townspeople = []
werewolf_conns = {}
townspeople_conns = {}
witch_conns= {}
wolftalktime = 60
wolfvotetime = 15
wolfkill = 0
wolfvote = -1
towntalktime = 60
townvotetime = 30

#Assign roles to players

def assign_roles(size, numWolves, numWitches):
    numPlayers = size
    roles = ['townsperson'] * numPlayers
    if numWolves + numWitches <= numPlayers:
        random_indices = random.sample(range(numPlayers), numWolves + numWitches)
        for i in random_indices[:numWolves]:
            roles[i] = 'werewolf'
        for i in random_indices[numWolves:numWolves + numWitches]:
            roles[i] = 'witch'
    return roles

def send_all(message):
    for i,client_comm in conns.items():
        client_comm.isend(message, dest=0)

def broadcasts(message,client):
    for i,comm in client.items():
        comm.isend(message, dest=0)

def create_communicators(conns):
    global werewolf_conns, townspeople_conns, witch_conns
    werewolf_conns = {idx: comm for idx, comm in conns.items() if idx in wolves}
    townspeople_conns = {idx: comm for idx, comm in conns.items() if idx in townspeople}
    witch_conns = {idx: comm for idx, comm in conns.items() if idx in witch}

def is_unanimous(votes, werewolf_conns):
    """Check if all voting werewolves voted for the same townspeople."""
    if len(votes) == 0:
        return False, None
    first_vote = list(votes.values())[0]
    return all(vote == first_vote for vote in votes.values()), int(first_vote)

def werewolf_discussion(werewolf_conns):
    global wolftalktime
    """
    Listens for messages from each werewolf and relays them to all other werewolves.

    Parameters:
    - werewolf_conns (dict of int: MPI.Intercomm): Dictionary of werewolf player indices to their MPI intercommunicator objects.
    """
    start_time = time.time()
    for _, comm in werewolf_conns.items():
        comm.send("discuss", dest=0, tag=102)
    active = True
    while active:
        for sender_idx, sender_comm in werewolf_conns.items():
            # Non-blocking check for a new message from each werewolf
            if sender_comm.Iprobe(source=0, tag=102):  # Check if there's a message
                message = sender_comm.recv(source=0,tag=102)  # Receive the message
                print(f"Player{sender_idx}: {message}")
                sys.stdout.flush()

                # Relay this message to all other werewolves
                for receiver_idx, receiver_comm in werewolf_conns.items():
                    if receiver_idx != sender_idx:  # Do not send the message back to the sender
                        receiver_comm.send(f'Player{sender_idx}:{message}', dest=0, tag=102)

        # Determine the condition to stop the server's relaying function
        if (time.time() - start_time) > wolftalktime:
            active = False
    
    # End discussion
    for _, comm in werewolf_conns.items():
        comm.send("discussion over", dest=0, tag=102)

def werewolf_votes(werewolf_conns,townspeople):
    global wolfvotetime, wolfkill, wolfvote
    """
    Listens for votes from werewolves, validates them against the active townspeople list,
    ensures each werewolf votes only once, and processes the votes. Ends voting when vote_time is over.

    Parameters:
    - werewolf_conns (dict): Dictionary of werewolf player indices to their MPI intercommunicator objects.
    - active_townspeople (list): List indicating whether each townspeople is active.
    - vote_time (float): Duration in seconds that the voting phase should last.
    """
    start_time = time.time()
    votes = {}
    voted_werewolves = set()  # Set to track which werewolves have already voted

    while True:
        # Check if voting time is over
        if time.time() - start_time >= wolfvotetime:
            print("Voting time has ended.")
            break

        for idx, player_comm in werewolf_conns.items():
            if idx not in voted_werewolves and player_comm.Iprobe(source=0):
                vote = player_comm.recv(source=0)
                if int(vote) in townspeople:
                    votes[idx] = vote
                    voted_werewolves.add(idx)  # Record that this werewolf has voted
                    print(f"Valid vote received from werewolf {idx} for player {vote}")
                    sys.stdout.flush()
                else:
                    player_comm.send("invalid vote",dest=0)
                    print(f"Invalid vote from werewolf {idx} for index {vote}")
                    sys.stdout.flush()

    # Process votes here, e.g., tallying votes to determine if a townspeople is eliminated
    print("Collected votes:", votes)
    sys.stdout.flush()
    unanimous, target = is_unanimous(votes, werewolf_conns)
    if unanimous and target is not None and (int(vote) in townspeople):
        # Mark the townspeople as inactive
        comm = conns[target]
        comm.send(f"You have been voted out by the werewolves.  You will be removed from the game.", dest=0)
        comm.send("close",dest=0)
        del conns[target]
        townspeople.remove(target)
        print(f"Player {target} unanimously voted out and will be removed.")
        sys.stdout.flush()
        wolfkill = 1
        wolfvote = target
    else:
        print("No unanimous vote.")
        sys.stdout.flush()

def day_discussion(all_conns):
    global towntalktime
    """
    Facilitates a discussion among all game members during the day phase.

    Parameters:
    - all_conns (dict of int: MPI.Intercomm): Dictionary of all player indices to their MPI intercommunicator objects.
    - dayTalkTime (float): Amount of time in seconds allocated for the day discussion phase.
    """
    start_time = time.time()
    
    # Notify all players to start discussing
    for _, comm in all_conns.items():
        comm.send("discuss", dest=0, tag=200)  # Using a different tag for day phase

    active = True
    while active:
        for sender_idx, sender_comm in all_conns.items():
            # Non-blocking check for a new message from each player
            if sender_comm.Iprobe(source=0, tag=102):  # Check if there's a message using the day phase tag
                message = sender_comm.recv(source=0, tag=102)
                print(f"Player{sender_idx}: {message}")
                sys.stdout.flush()

                # Relay this message to all other players
                for receiver_idx, receiver_comm in all_conns.items():
                    if receiver_idx != sender_idx:
                        receiver_comm.send(f'Player{sender_idx}: {message}', dest=0, tag=102)

        # Check if the discussion time has elapsed
        if (time.time() - start_time) > towntalktime:
            active = False

    # Notify all players that the discussion is over
    for _, comm in all_conns.items():
        comm.send("discussion over", dest=0, tag=200)  # Ending the discussion phase with the same tag

def standardTurn():
    global wolftalktime, wolfkill, wolfvote, towntalktime, townvotetime
    wolfkill = 0
    witchkill = 0
    message = "Night falls and the town sleeps.  Everyone close your eyes"
    send_all(message)
    #**************WEREWOLVES************************
    if len(wolves) < 2: wolftalktime = 0
    message = "Werewolves, open your eyes."
    broadcasts(message,werewolf_conns)
    message = f'Werewolves, {wolves}, you must choose a victim.  You have {wolftalktime} seconds to discuss.  Possible victims are {townspeople}'
    broadcasts(message,werewolf_conns)
    werewolf_discussion(werewolf_conns)
    message = f'Werewolves, you must vote on a victim to eat.  You have {wolfvotetime} seconds to vote.  Valid votes are {townspeople}.'
    broadcasts(message,werewolf_conns)
    werewolf_votes(werewolf_conns,townspeople)
    broadcasts('Werewolves, go to sleep.',werewolf_conns)
    #**********END WEREWOLVES************************

    #**************START TOWN***********************
    if wolfkill ==1:
        send_all(f'Wolves killed player{wolfvote}')
    else:
        send_all("No one was killed.")
    if len(wolves) == 0 or len(conns) == len(wolves):
            return 1
    send_all(f'It is day.  Everyone, open your eyes.  You will have {towntalktime} seconds to discuss who the werewolves are.')
    print('Day-townspeople debate')
    sys.stdout.flush()
    day_discussion(conns)
    send_all(f'Townspeople, you have {townvotetime} seconds to cast your votes on who to hang. Valid votes are {conns.keys()}')
    #******************END TOWN*******************

if rank == 0:
    port_name = MPI.Open_port()
    print(f"Server listening on port: {port_name}")
    sys.stdout.flush()

    with open('port_name.txt', 'w') as file:
        file.write(port_name)

    connections = 0  # To track and assign unique player ranks
    start_time = time.time()

    print("Waiting for client connections...")
    sys.stdout.flush()
    while time.time() - start_time < 30:
        try:
            client_comm = comm.Accept(port_name, info=MPI.INFO_NULL)
            if client_comm != MPI.COMM_NULL:  # Check if a connection was accepted
                player_rank = connections  # Assign a unique player rank
                conns[player_rank] = client_comm
                print(f"Player{player_rank} connected.")
                sys.stdout.flush()
                message = f'Hello, Player{player_rank}. You are connected. Please wait for the game to start.'
                conns[player_rank].isend(message, dest=0, tag=0)
                connections += 1
        except: pass
        time.sleep(0.1)
    print("No longer accepting connections.")
    sys.stdout.flush()

    comm.barrier() # Wait for all players to connect to the game

    roles = assign_roles(connections, 2, 1)
    # Send roles to each player
    for i,client_comm in conns.items():
        client_comm.send(roles[i], dest=0)
    print("roles assigned")
    sys.stdout.flush()

    players = list(range(connections))
    wolves = [players[i] for i, role in enumerate(roles) if role == 'werewolf']
    townspeople = [players[i] for i, role in enumerate(roles) if role == 'townsperson']
    witch = [players[i] for i, role in enumerate(roles) if role == 'witch']
    print(f'wolves: {wolves}')
    print(f'townspeople: {townspeople}')
    print(f'witch: {witch}')

    create_communicators(conns)
    print("Communicators created")
    sys.stdout.flush()

    message = 'There are ' + str(len(wolves)) + ' wolves, and ' + str(len(conns) - len(wolves)) + ' townspeople.'
    send_all(message)
    
    comm.barrier()

    # Night phase
    print("Night phase starting.")
    #targets = collect_night_actions()
    print("Night actions received:")
    sys.stdout.flush()
    standardTurn()

    if len(wolves) == 0: 
        winner = 'Townspeople win'
    elif len(wolves) == len(conns): 
        winner = 'Werewolves win'
    send_all(winner)
    send_all('close')


    
