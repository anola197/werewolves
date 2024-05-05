# Werewolves Game using MPI

This project implements a multiplayer werewolf game using MPI (Message Passing Interface), allowing players to participate in a virtual version of the popular social deduction game. The game supports multiple players, each taking on roles as either townspeople or werewolves, with the main objective of the townspeople being to eliminate the werewolves and the werewolves aiming to eliminate the townspeople.

## Features

- **Role Assignment**: At the start of the game, players are randomly assigned roles as either werewolves or townspeople.
- **Night Phase**: During the night, werewolves secretly choose a townspeople to eliminate.
- **Day Phase**: During the day, all players participate in a discussion and vote on who they suspect is a werewolf.
- **Voting System**: Implements a voting mechanism where players can vote for who they suspect and, based on majority, potentially eliminate that player from the game.
- **Dynamic Discussion**: All Players can discuss during the day phase and werewolves can discuss during the night phase through a chat system facilitated by MPI.

## Requirements

- Python 3.12
- mpi4py (Tested with version 3.1.6)
- An MPI implementation like MPICH or OpenMPI

## Setup and Installation

1. **Install MPI**:
   - For Ubuntu: `sudo apt install mpich`
   - For macOS: `brew install mpich`

2. **Install mpi4py**:
    - Ensure pip is updated: `pip3 install --upgrade pip3`
   - Install mpi4py: `pip3 install mpi4py`
   - You can create virtual env as well to install mpi4py python library.
      - `python3 -m venv venv`
      - `pip3 install mpi4py`
      - `source venv/bin/activate` 

3. **Gamr installation**:
   - Unpack the tar file.: `werewolves_mpi.tgz`. Use the server and the client files to connect to the game

## Running the Game

1. To start the game server:
   - `mpiexec -n 1 python3 server.py`
2. To start the client:
   - `mpiexec -n 1 python3 client.py`

## Future Scope
- Implement a better client server connection system. In current sceanrio MPI_Comm_Accept is blocking call last player connection to be sent after the timeout or else it will be stuck on Accept. 
- To improve scalability, consider implementing a mechanism where the server can handle connections in a more distributed manner.
- Implementing functionality to dynamically add or remove clients during runtime without stopping the game could be a significant improvement.
- Adding functionality for other roles such as witch
