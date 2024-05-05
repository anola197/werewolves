from mpi4py import MPI
import time
import sys
import random
import threading

#read in config file

i = {}
inputVars = open('config', 'r').read().split('\n')
for var in inputVars:
    var = var.strip('\n').split('=')
    key = var[0]
    try:#if a line doesn't have an = sign
        value = var[1]
    except:
        continue
    i[key] = value

#time parameters
timeTillStart = int(i['timeTillStart'])
wolftalktime = int(i['wolfTalkTime'])
wolfvotetime = int(i['wolfVoteTime'])
townvotetime = int(i['townVoteTime'])
towntalktime = int(i['townTalkTime'])
timeout = int(i['connectiontimeout'])

comm = MPI.COMM_WORLD
rank = comm.Get_rank()
conns = {}
winner = 'No winner'
wolves = []
witch =[]
townspeople = []
werewolf_conns = {}
townspeople_conns = {}
#witch_conns= {}
wolfkill = 0
wolfvote = -1
connections = 0


def handle_connections_merge(port_name):
    global conns, connections, timeout, comm
    start_time = time.time()
    all_comm = comm  # Initialize all_comm with the original communicator
    while time.time() - start_time < timeout:
        try:
            client_comm = comm.Accept(port_name, info=MPI.INFO_NULL)
            if client_comm != MPI.COMM_NULL:
                player_rank = connections  # Use a mutable object to maintain state
                #conns[player_rank] = client_comm
                print(f"Player{player_rank} connected.")
                sys.stdout.flush()
                print(all_comm)
                sys.stdout.flush()
                # Merge the new communicator with the existing one
                new_comm = client_comm.Merge(high=False)
                print(new_comm)
                sys.stdout.flush()
                #all_comm.Free()  # Free the old communicator
                all_comm = new_comm  # Update all_comm to the newly merged communicator
                print(all_comm)
                message = f'Hello, Player{player_rank}. You are connected. Please wait for the game to start.'
                all_comm.isend(message, dest=1)
                connections += 1
        except Exception as e:
            print(f"Error accepting connection: {e}")
            break
        time.sleep(0.1)
    MPI.Close_port(port_name)
    return all_comm 

def handle_connections_test(port_name):
    global conns, connections, timeout, comm
    start_time = time.time()
    #comm.Exception_set_timeout(10)  # Set timeout to 30 seconds
    try:
        while time.time() - start_time < timeout:
            client_comm = comm.Accept(port_name, info=MPI.INFO_NULL)
            if client_comm != MPI.COMM_NULL:
                player_rank = connections  # Use a mutable object to maintain state
                conns[player_rank] = client_comm
                print(f"Player{player_rank} connected.")
                sys.stdout.flush()
                message = f'Hello, Player{player_rank}. You are connected. Please wait for the game to start.'
                conns[player_rank].isend(message, dest=0)
                connections += 1
        return True
    except MPI.Exception as e:
        print(f"Error accepting connection: {e}")
        sys.stdout.flush()
        print("Timeout reached. No clients connected within the specified time.")
        return False
        
def handle_connections(port_name):
    global conns, connections, timeout,comm
    start_time = time.time()
    while time.time() - start_time < timeout:
            try:
                client_comm = comm.Accept(port_name, info=MPI.INFO_NULL)
                if client_comm != MPI.COMM_NULL:
                    player_rank = connections  # Use a mutable object to maintain state
                    conns[player_rank] = client_comm
                    print(f"Player{player_rank} connected.")
                    sys.stdout.flush()
                    message = f'Hello, Player{player_rank}. You are connected. Please wait for the game to start.'
                    conns[player_rank].isend(message, dest=0)
                    connections += 1
            except Exception as e:
                print(f"Error accepting connection: {e}")
                break
            time.sleep(0.1)
    MPI.Close_port(port_name)
#Assign roles to players
def assign_roles(size, numWolves):
    numPlayers = size
    roles = ['townsperson'] * numPlayers
    if numWolves <= numPlayers:
        random_indices = random.sample(range(numPlayers), numWolves)
        for i in random_indices[:numWolves]:
            roles[i] = 'werewolf'
        #for i in random_indices[numWolves:numWolves + numWitches]:
        #    roles[i] = 'witch'
    return roles
#Broadcast to all users
def send_all(message):
    for i,client_comm in conns.items():
        client_comm.isend(message, dest=0)
#Broadcast to desired groups
def broadcasts(message,client):
    for i,comm in client.items():
        comm.isend(message, dest=0)

def is_unanimous(votes, werewolf_conns):
    """Check if all voting werewolves voted for the same townspeople."""
    if len(votes) == 0:
        return False, None
    first_vote = list(votes.values())[0]
    return all(vote == first_vote for vote in votes.values()), int(first_vote)

def create_communicators(conns):
    global werewolf_conns, townspeople_conns
    werewolf_conns = {idx: comm for idx, comm in conns.items() if idx in wolves}
    townspeople_conns = {idx: comm for idx, comm in conns.items() if idx in townspeople}
    #witch_conns = {idx: comm for idx, comm in conns.items() if idx in witch}

def werewolf_discussion(werewolf_conns):
    global wolftalktime
    """
    Listens for messages from each werewolf and relays them to all other werewolves.

    Parameters:
    - werewolf_conns (dict of int: MPI.Intercomm): Dictionary of werewolf player indices to their MPI intercommunicator objects.
    """
    start_time = time.time()
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
                if vote.isdigit() and int(vote) in townspeople:
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
        del townspeople_conns[target]
        print(f"Player {target} unanimously voted out and will be removed.")
        sys.stdout.flush()
        wolfkill = 1
        wolfvote = target
    else:
        print("No unanimous vote.")
        sys.stdout.flush()

def collect_votes(player_conns, voting_time):
    global werewolf_conns, townspeople_conns
    """
    Collects votes from all players during the day phase to identify a suspected werewolf.

    Parameters:
    - player_conns (dict): Dictionary mapping player indices to their MPI intercommunicator objects.
    - voting_time (float): The duration in seconds that voting is allowed to last.
    """
    start_time = time.time()
    votes = {}
    all = player_conns.keys()

    # Collect votes from all players
    while time.time() - start_time < voting_time:
        for idx, conn in player_conns.items():
            if conn.Iprobe(source=0, tag=102):
                vote = conn.recv(source=0, tag=102)
                if vote.isdigit() and int(vote) in all:
                    if idx not in votes:  # Ensure each player votes only once
                        votes[idx] = vote
                        print(f"Player {idx} voted for Player {vote}")
                        sys.stdout.flush()
                else:
                    print(f"Invalid vote from Player {idx} for Player {vote}")
                    sys.stdout.flush()

    # Evaluate votes to determine if any player has been voted out
    if votes:
        vote_list = list(votes.values())
        voted_player = max(set(vote_list), key=vote_list.count)
        target = int(voted_player)
        vote_count = vote_list.count(voted_player)
        if vote_count > len(players) // 2:  # Simple majority rule
            comm = conns[target]
            comm.send(f"You have been voted out by the villagers.  You will be removed from the game.", dest=0)
            comm.send("close",dest=0)
            del conns[target]
            if target in wolves:
                wolves.remove(target)
                del werewolf_conns[target]
            elif target in townspeople:
                townspeople.remove(target)
                del townspeople_conns[target]
            #elif target in witch:
            #    witch.remove(target)
            #    del witch_conns[target]
            print(f"Player {target} has been voted out by the villegers.")
            sys.stdout.flush()
        else:
            print("No player has been voted out.")
            sys.stdout.flush()

    for _, conn in conns.items():
        conn.send("voting over", dest=0, tag=102)  # Notify all players that voting is over

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
    #for _, comm in all_conns.items():
    #    comm.send("discuss", dest=0, tag=200)  # Using a different tag for day phase

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
    #for _, comm in all_conns.items():
    #    comm.send("discussion over", dest=0, tag=200)  # Ending the discussion phase with the same tag

def standardTurn():
    global wolftalktime, wolfkill, wolfvote, towntalktime, townvotetime
    wolfkill = 0
    witchkill = 0
    message = "Night falls and the town sleeps.  Everyone close your eyes"
    send_all(message)
    #**************WEREWOLVES************************
    if len(wolves) < 2: wolftalktime = 0
    broadcasts("Werewolves, open your eyes.",townspeople_conns)
    broadcasts(f'Werewolves, {wolves}, you must choose a victim.  You have {wolftalktime} seconds to discuss.  Possible victims are {townspeople}',werewolf_conns)
    print('Night-werewolves debate')
    werewolf_discussion(werewolf_conns)
    broadcasts('Werewolves, vote.',townspeople_conns)
    broadcasts(f'Werewolves, you must vote on a victim to eat.  You have {wolfvotetime} seconds to vote.  Valid votes are {townspeople}.',werewolf_conns)
    werewolf_votes(werewolf_conns,townspeople)
    broadcasts('Werewolves, go to sleep.',townspeople_conns)
    #**********END WEREWOLVES************************

    #**************START TOWN***********************
    if wolfkill ==1:
        send_all(f'Wolves killed player{wolfvote}')
    else:
        send_all("No one was killed.")
    print(conns)
    if len(wolves) == 0 or len(townspeople) < len(wolves):
            return 1
    send_all(f'It is day.  Everyone, open your eyes.  You will have {towntalktime} seconds to discuss who the werewolves are.')
    print('Day-townspeople debate')
    sys.stdout.flush()
    day_discussion(conns)
    send_all(f'Townspeople, you have {townvotetime} seconds to cast your votes on who to hang. Valid votes are {conns.keys()}')
    collect_votes(conns,30)
    #******************END TOWN*******************

#def main():
    #global conns, timeout, connections
if rank == 0:
    port_name = MPI.Open_port()
    print(f"Server listening on port: {port_name}")
    sys.stdout.flush()
    with open('port_name.txt', 'w') as file:
        file.write(port_name)
    #connections = 0  # To track and assign unique player ranks
    print("Waiting for client connections...")
    sys.stdout.flush()
    handle_connections_test(port_name)
    print("No longer accepting connections.")
    sys.stdout.flush()
    roles = assign_roles(connections, 2)
    # Send roles to each player
    print(roles)
    for i,client_comm in conns.items():
        client_comm.send(f'~~~~~ YOU ARE A {roles[i]} ~~~~~', dest=0)
    print("roles assigned")
    sys.stdout.flush()
    players = list(range(connections))
    wolves = [players[i] for i, role in enumerate(roles) if role == 'werewolf']
    townspeople = [players[i] for i, role in enumerate(roles) if role == 'townsperson']
    #witch = [players[i] for i, role in enumerate(roles) if role == 'witch']
    create_communicators(conns) # communicators for each group
    print('Begin')
    sys.stdout.flush()
    send_all('There are ' + str(len(wolves)) + ' wolves, and ' + str(len(conns) - len(wolves)) + ' townspeople.')
    
    round = 1
    while len(wolves) != 0 and len(wolves) <= len(townspeople):
        send_all('*' * 50)
        send_all('*' * 21 + 'ROUND ' + str(round) + '*' * 22)
        send_all('*' * 15 + str(len(conns)) + ' players remain.' + '*' * 18)
        send_all('*' * 50)
        print('Round ' + str(round))
        print(f'wolves: {wolves}')
        print(f'townspeople: {townspeople}')
        sys.stdout.flush()
        #print(f'witch: {witch}')
        standardTurn()
        round += 1
    if len(wolves) == 0: 
        winner = 'Townspeople win'
        sys.stdout.flush()
    elif len(wolves) > len(townspeople): 
        winner = 'Werewolves win'
    print(winner)
    send_all(winner)
    send_all("Game is over. Please reconnect your client to play again.")
    send_all('close')


