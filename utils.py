import pickle
import copy
import random

import numpy as np

ILLEGAL = -1
NORMAL = 1
PUSH = 2
WIN = 10000

num_layers = 12
size = 20


class PushPosition:
    """
    A PushPosition is a board position allowing the action
    space to be discretized by pushes.
    Discretizing by moves is also permitted for the sake of gameplay.
    In each case, penalties are move-wise, not push-wise.   
    The PushPosition is initialized with an array of shape
    (size, size, 10).  Only the first five layers need to be filled in.
    Current layers: Unmovables, movables, character, winspace, empty
    space, empty space accessible from current character location
    (value is 1), blocks which can be
    pushed in directions 0, 1, 2, 3 (value is -# of moves).
    Locations of exits which can be reached are on layer 10.
    Layer 11 is the number of times a square was empty and accessible.
    Note that the exit and character squares are considered empty.
    """
    
    def __init__(self, arr):
        """
        Initializes the position.  The first five planes define the
        level.  The remaining layers are ignored and recomputed.
        """
        # Allowing for adding input planes
        if arr.shape[2] < num_layers:
            new_arr = np.zeros((size, size, num_layers))
            new_arr[:,:,0:arr.shape[2]] = arr
            arr = new_arr
        self.size = arr.shape[1]
        self.arr = arr
        self.moves = []
        for x in range(self.size):  # Locate character
            for y in range(self.size):
                if arr[x, y, 2] == 1:
                    self.char_loc = [x, y]
                if arr[x, y, 3] == 1:
                    self.exit_loc = [x, y]
        # Clear the extra layers
        self.arr[:,:,5:] = np.zeros((self.size, self.size, num_layers-5))
        self.moves_penalty = 0
        self.assign_pushes()
        
    def is_unmovable(self, x, y):
        return (self.arr[x, y, 0] == 1)
    
    def is_movable(self, x, y):
        return (self.arr[x, y, 1] == 1)
    
    def is_char(self, x, y):
        return (self.arr[x, y, 2] == 1)
        
    def is_win(self, x, y):
        return (self.arr[x, y, 3] == 1)
    
    def is_empty(self, x, y):
        return (self.arr[x, y, 4] == 1)
        
    def assign_pushes(self):
        """
        Only for internal use.
        Whenever the position is initialized or updated, this checks
        all available pushes from the current position.
        """        
        self.arr[:,:,5:] = np.zeros((self.size, self.size, num_layers-5))
        self.arr[self.char_loc[0], self.char_loc[1], 5] = 1
        number_moves = 0
        squares = [self.char_loc]  # Tracks unexplored squares
        vecs = [[-1, 0], [0, 1], [1, 0], [0, -1]]
        while len(squares) > 0:
            number_moves += 1
            new_squares = []
            for square in squares:
                for move in range(4):
                    self.append_square(new_squares, square,
                                       vecs[move], move, number_moves)
            squares = new_squares
        self.arr[:,:,11] += self.arr[:,:,5]
        
    def in_bounds(self, x, y):
        return (x >= 0 and y >= 0 and x < self.size and y < self.size)
                    
    def make_move(self, x, y, direction, notifying_illegal = False):
        """
        Makes a pushwise move at (x,y) in one of the four directions.
        """
        if (not self.in_bounds(x, y)) or self.arr[x, y, direction+6] == 0:
            if notifying_illegal:
                print("Illegal move")
            return ILLEGAL
        vecs = [[-1, 0], [0, 1], [1, 0], [0, -1]]
        self.moves.append(np.array([x, y, direction]))  # Tracks moves pushwise
        # Won without pushing
        if self.is_win(x, y) and not self.is_movable(x, y):
            self.moves_penalty += self.arr[x, y, 10]
            return WIN  # Should not play more moves after this
        self.moves_penalty += self.arr[x, y, direction+6]
        # Won with pushing
        if self.is_win(x, y):
            return WIN
        # Three planes to update: character, movable, empty.
        self.arr[self.char_loc[0], self.char_loc[1], 2] = 0
        self.arr[x, y, 1] = 0
        self.arr[x, y, 2] = 1
        self.arr[x, y, 4] = 1
        self.arr[x+vecs[direction][0], y+vecs[direction][1], 4] = 0
        self.arr[x+vecs[direction][0], y+vecs[direction][1], 1] = 1
        self.char_loc = [x, y]
        # Maintain the possible pushes plane
        self.assign_pushes()
        return PUSH
        
    def make_move_number(self, move):
        """
        Handles decoding for move numbers used by net.
        The move is encoded using three variables: x position,
        y position, and the direction of the push.
        """
        x = move//((self.size*2-1)*4) + self.char_loc[0] - (size-1)
        y = (move%((self.size*2-1)*4))//4 + self.char_loc[1] - (size-1)
        direction = move%4
        return self.make_move(x, y, direction)

    def move_in_direction(self, direction):
        """
        Moves in a direction for the sake of gameplay.
        Output is true if and only if the move is legal.
        """
        vec = [[-1, 0], [0, 1], [1, 0], [0, -1]][direction]
        new_x = self.char_loc[0] + vec[0]
        new_y = self.char_loc[1] + vec[1]
        if not self.in_bounds(new_x, new_y):
            return False
        # If the requested move is not a legal push
        if self.arr[new_x, new_y, direction+6] == 0:
            # If the requested move hits something
            if (self.is_unmovable(new_x, new_y)
                or self.is_movable(new_x, new_y)):
                return False
            # The move is now known to be legal.
            self.arr[self.char_loc[0], self.char_loc[1], 2] = 0
            self.arr[new_x, new_y, 2] = 1
            self.char_loc = [new_x, new_y]
            # Now need to redo planes with new distances
            self.assign_pushes()
            self.moves_penalty += 1
            return True
        # If the requested move is a legal push or win
        self.moves_penalty += 1
        self.make_move(new_x, new_y, direction)
        return True
        
                    
    def append_square(self, new_squares, square, vec, move, num_moves):
        """
        Only for internal use.
        Checks whether the square can be reached.
        If it is empty, add it to plane 5.
        If it contains a block that can be pushed or an exit, add
        it to planes 6-9 inclusive as appropriate.
        Maintains the new_squares list from its caller.
        """
        x = square[0] + vec[0]
        y = square[1] + vec[1]
        # Out of bounds
        if not self.in_bounds(x, y):
            return
        # Empty space with no winspace
        if self.is_empty(x, y) and not self.is_win(x, y):
            if self.arr[x, y, 5] == 1:  # Already explored
                return
            self.arr[x, y, 5] = 1
            new_squares.append([x, y])  # Need to explore this square
            return
        # Winspace
        if self.is_win(x, y) and self.is_empty(x, y):
            # Already entered winspace at least as quickly
            if np.sum(self.arr[x, y, 6:10]) != 0:
                return
            # Newly entering winspace and valid to enter
            # No associated orientation.  Also update plane 10.
            self.arr[x, y, move+6] = -num_moves
            self.arr[x, y, 10] = -num_moves
            return
        # The only remaining legal case is a pushable movable.
        if not self.in_bounds(x+vec[0], y+vec[1]):
            return
        if self.is_movable(x, y) and self.is_empty(x+vec[0], y+vec[1]):
            self.arr[x, y, move+6] = -num_moves
            # Now account for possible win
            # It may be possible to push from multiple directions.
            # We want the shorter one, so take the max.
            if self.is_win(x, y):
                self.arr[x, y, 10] = max(self.arr[x, y, 10], -num_moves)
            
    def prettystring(self):
        """Prints the board in a somewhat human-readable format"""
        out = ""
        for i in range(self.size):
            for j in range(self.size):
                if self.arr[i,j,0] == 1:
                    out += "U"
                elif self.arr[i,j,1] == 1:
                    out += "M"
                    if self.arr[i,j,3] == 1:
                        out += "W"
                elif self.arr[i,j,2] == 1:
                    out += "C"
                elif self.arr[i,j,3] == 1:
                    out += "W"
                elif self.arr[i,j,4] == 1:
                    out += "-"
            out += "\n"
        return out

        
def append_level_data(file_string, data_x, data_y):
    f = open(file_string, "rb")
    lvl_data = pickle.load(f)
    f.close()
    arr, char_loc, steps = np.array(lvl_data[0]), lvl_data[1], lvl_data[2]
    # This data is stepwise (since it was produced by user gameplay).
    # Need to convert it to pushwise data.
    size = arr.shape[0]
    vecs = [[-1, 0], [0, 1], [1, 0], [0, -1]]
    push_pos = PushPosition(arr)
    x_rotations(centered(copy.deepcopy(push_pos.arr),
                         char_loc[0], char_loc[1]),
                data_x)
    prev_char_x, prev_char_y = push_pos.char_loc
    for step in steps:
        vec = vecs[step]
        new_char_x = push_pos.char_loc[0]+vec[0]
        new_char_y = push_pos.char_loc[1]+vec[1]
        if (push_pos.is_movable(new_char_x, new_char_y)
            or push_pos.is_win(new_char_x, new_char_y)):
            y_rotations(new_char_x+size-1-prev_char_x,
                        new_char_y+size-1-prev_char_y,
                        step, data_y)
            if not push_pos.move_in_direction(step):
                print("Level did not load properly.")
            x_rotations(centered(copy.deepcopy(push_pos.arr), new_char_x,
                                               new_char_y), data_x)
            prev_char_x, prev_char_y = new_char_x, new_char_y
        else:
            if not push_pos.move_in_direction(step):
                print("Level did not load properly.")
    # Have to get rid of the position that appears after the win
    del data_x[-8:]
    #del data_x[-1:]
    
    
def centered(arr, char_x, char_y):
    """
    Puts the size by size level in a centered 2*size-1 by
    2*size-1 level padded with unmovables.
    """
    global size
    new_arr = np.zeros((2*size-1, 2*size-1, num_layers))
    new_arr[:,:,0] = np.ones((2*size-1, 2*size-1))
    new_arr[size-1-char_x:2*size-1-char_x,
            size-1-char_y:2*size-1-char_y,
            :] = arr
    return new_arr

            
def x_rotations(arr, data_x):
    """
    Computes all rotations of an input board.
    """
    cop_arr = copy.deepcopy(arr)
    for i in range(4):
        data_x.append(copy.deepcopy(cop_arr))
        cop_arr = np.rot90(cop_arr)  # Rotate
        # Now have to fix pushes
        cop_arr[:,:,6:10] = np.roll(cop_arr[:,:,6:10], -1, axis=2)
    cop_arr = cop_arr.swapaxes(0, 1)  # Reflect
    cop_arr[:,:,6:10] = np.flip(cop_arr[:,:,6:10], 2)
    for i in range(4):
        data_x.append(copy.deepcopy(cop_arr))
        cop_arr = np.rot90(cop_arr)
        cop_arr[:,:,6:10] = np.roll(cop_arr[:,:,6:10], -1, axis=2)
    cop_arr[:,:,6:10] = np.flip(cop_arr[:,:,6:10], 2)
    cop_arr = cop_arr.swapaxes(0, 1)


def rotate_once(x, y, direction):
    global size
    return (2*size-1)-y-1, x, (direction-1) % 4

        
def y_rotations(x, y, direction, data_y):
    """
    Translates move numbers to match the rotations of the
    input board.
    """
    # DOUBLE CHECK THIS
    global size
    dsize = 2*size-1
    for i in range(4):
        data_y.append(onehot(dsize*dsize*4, 4*dsize*x + 4*y + direction))
        x, y, direction = rotate_once(x, y, direction)
    direction = 3 - direction
    x, y = y, x
    for i in range(4):
        data_y.append(onehot(dsize*dsize*4, 4*dsize*x + 4*y + direction))
        x, y, direction = rotate_once(x, y, direction)
    x, y = y, x
    direction = 3 - direction

                        
def load_levels(levels, solved_path):
    """Makes data out of solved levels"""
    data_x = []
    data_y = []
    for level in levels:
        print(level)
        append_level_data(solved_path+level, data_x, data_y)
    return np.array(data_x), np.array(data_y)

    
def import_raw_level(level, raw_path):
    """
    Imports a level given the level code in the official PP2 format.
    Pads the level with unmovables to make it 20x20.
    """
    f = open(raw_path+level+".txt", "r")
    level = f.readline().split()  
    metadata = level[0].split(",")
    width, height = int(metadata[2]), int(metadata[3])
    arr = np.zeros((20, 20, 10))
    arr[:,:,4] = 1
    for i in range(0, 20):
        for j in range(0, 20):
            if i >= height or j >= width:
                arr[i,j,0] = 1
                arr[i,j,4] = 0
    for item in level[1:]:
        vals = item.split(":")[1].split(",")
        if item[0] == "w":
            arr[int(vals[1]),int(vals[0]),3] = 1
        if item[0] == "b":
            arr[int(vals[1]),int(vals[0]),0] = 1
            arr[int(vals[1]),int(vals[0]),4] = 0
        if item[0] == "m":
            arr[int(vals[1]),int(vals[0]),1] = 1
            arr[int(vals[1]),int(vals[0]),4] = 0
        if item[0] == "c":
            arr[int(vals[1]),int(vals[0]),2] = 1
    p = PushPosition(arr)
    return p, width, height

        
def onehot(length, ind):
    out = np.zeros((length))
    out[ind] = 1
    return out

    
def get_position(arr, moves):
    """
    Fetches a PushPosition based on the initial array and the
    moves list.  Moves are discretized by pushes.
    """
    p = PushPosition(arr)
    for move in moves:
        p.make_move(move[0], move[1], move[2], notifying_illegal = True)
    return p

    
def set_up_position(pass_in, size_x, size_y): #setting up a position given an array of 0, 1, 2, etc.
    arr = np.zeros((20, 20, num_layers))
    arr[:,:,0] = np.ones((20, 20))
    arr[:size_x, :size_y, 0] = np.zeros((size_x, size_y))
    for x in range(size_x):
        for y in range(size_y):
            if pass_in[x, y] < 5: #want to allow both movable and exit
                arr[x,y,pass_in[x, y]] = 1
            else:
                arr[x,y,1] = 1
                arr[x,y,3] = 1
    return PushPosition(arr)

    
def shuffle_in_unison(l1, l2):
    c = list(zip(l1, l2))
    random.shuffle(c)
    out1, out2 = zip(*c)
    out1 = list(out1)
    out2 = list(out2)
    return out1, out2

#testing code    
#data_x, data_y = load_levels(["Sandstorm"], "SolvedLevels\\")
#ind = 1
#print(PushPosition(data_x[ind]).prettystring())
#print(np.argmax(data_y[ind]))