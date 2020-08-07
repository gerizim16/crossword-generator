import sys
from itertools import combinations
from queue import SimpleQueue

from crossword import *


class CrosswordCreator():
    def __init__(self, crossword):
        """
        Create new CSP crossword generate.
        """
        self.crossword = crossword
        self.domains = {
            var: self.crossword.words.copy()
            for var in self.crossword.variables
        }

    def letter_grid(self, assignment):
        """
        Return 2D array representing a given assignment.
        """
        letters = [[None for _ in range(self.crossword.width)]
                   for _ in range(self.crossword.height)]
        for variable, word in assignment.items():
            direction = variable.direction
            for k in range(len(word)):
                i = variable.i + (k if direction == Variable.DOWN else 0)
                j = variable.j + (k if direction == Variable.ACROSS else 0)
                letters[i][j] = word[k]
        return letters

    def print(self, assignment):
        """
        Print crossword assignment to the terminal.
        """
        letters = self.letter_grid(assignment)
        for i in range(self.crossword.height):
            for j in range(self.crossword.width):
                if self.crossword.structure[i][j]:
                    print(letters[i][j] or " ", end="")
                else:
                    print("█", end="")
            print()

    def save(self, assignment, filename):
        """
        Save crossword assignment to an image file.
        """
        from PIL import Image, ImageDraw, ImageFont
        cell_size = 100
        cell_border = 2
        interior_size = cell_size - 2 * cell_border
        letters = self.letter_grid(assignment)

        # Create a blank canvas
        img = Image.new("RGBA", (self.crossword.width * cell_size,
                                 self.crossword.height * cell_size), "black")
        font = ImageFont.truetype("assets/fonts/OpenSans-Regular.ttf", 80)
        draw = ImageDraw.Draw(img)

        for i in range(self.crossword.height):
            for j in range(self.crossword.width):

                rect = [(j * cell_size + cell_border,
                         i * cell_size + cell_border),
                        ((j + 1) * cell_size - cell_border,
                         (i + 1) * cell_size - cell_border)]
                if self.crossword.structure[i][j]:
                    draw.rectangle(rect, fill="white")
                    if letters[i][j]:
                        w, h = draw.textsize(letters[i][j], font=font)
                        draw.text(
                            (rect[0][0] + ((interior_size - w) / 2),
                             rect[0][1] + ((interior_size - h) / 2) - 10),
                            letters[i][j],
                            fill="black",
                            font=font)

        img.save(filename)

    def solve(self):
        """
        Enforce node and arc consistency, and then solve the CSP.
        """
        self.enforce_node_consistency()
        self.ac3()
        return self.backtrack(dict())

    def enforce_node_consistency(self):
        """
        Update `self.domains` such that each variable is node-consistent.
        (Remove any values that are inconsistent with a variable's unary
         constraints; in this case, the length of the word.)
        """
        for var in self.crossword.variables:
            self.domains[var] = set(word for word in self.domains[var]
                                    if len(word) == var.length)

    def revise(self, x, y):
        """
        Make variable `x` arc consistent with variable `y`.
        To do so, remove values from `self.domains[x]` for which there is no
        possible corresponding value for `y` in `self.domains[y]`.

        Return True if a revision was made to the domain of `x`; return
        False if no revision was made.
        """
        # Check if there is an overlap
        overlap = self.crossword.overlaps[x, y]
        if overlap is None:
            return False

        i, j = overlap
        remove_set = set()
        for x_word in self.domains[x]:
            if not any(x_word[i] == y_word[j] for y_word in self.domains[y]):
                remove_set.add(x_word)
        self.domains[x] -= remove_set
        return bool(remove_set)

    def ac3(self, arcs=None):
        """
        Update `self.domains` such that each variable is arc consistent.
        If `arcs` is None, begin with initial list of all arcs in the problem.
        Otherwise, use `arcs` as the initial list of arcs to make consistent.

        Return True if arc consistency is enforced and no domains are empty;
        return False if one or more domains end up empty.
        """
        # Create arcs if None
        if arcs is None:
            arcs = SimpleQueue()
            for x in combinations(self.crossword.variables, 2):
                arcs.put(x)

        while not arcs.empty():
            x, y = arcs.get()
            if self.revise(x, y):
                if not self.domains[x]:
                    return False
                neighbors = self.crossword.neighbors(x)
                neighbors.remove(y)
                for x_neighbor in neighbors:
                    arcs.put((x_neighbor, x))
        return True

    def assignment_complete(self, assignment):
        """
        Return True if `assignment` is complete (i.e., assigns a value to each
        crossword variable); return False otherwise.
        """
        return all(var in assignment for var in self.crossword.variables)

    def consistent(self, assignment):
        """
        Return True if `assignment` is consistent (i.e., words fit in crossword
        puzzle without conflicting characters); return False otherwise.
        """
        # Check if words are unique and of correct length
        encountered_words = set()
        for var, word in assignment.items():
            if var.length != len(word) or word in encountered_words:
                return False
            encountered_words.add(word)

        # Check for overlap constraint
        for x, y in combinations(assignment, 2):
            overlap = self.crossword.overlaps[x, y]
            if overlap is None:
                continue
            i, j = overlap
            if assignment[x][i] != assignment[y][j]:
                return False

        return True

    def order_domain_values(self, var, assignment):
        """
        Return a list of values in the domain of `var`, in order by
        the number of values they rule out for neighboring variables.
        The first value in the list, for example, should be the one
        that rules out the fewest values among the neighbors of `var`.
        """
        def getWordValue(word):
            unassigned_neighbors = set(
                self.crossword.neighbors(var)) - set(assignment)

            count = 0
            for neighbor in unassigned_neighbors:
                for neighbor_word in self.domains[neighbor]:
                    i, j = self.crossword.overlaps[var, neighbor]
                    if word[i] != neighbor_word[j]:
                        count += 1
            return count

        return sorted(list(self.domains[var]), key=getWordValue)

    def select_unassigned_variable(self, assignment):
        """
        Return an unassigned variable not already part of `assignment`.
        Choose the variable with the minimum number of remaining values
        in its domain. If there is a tie, choose the variable with the highest
        degree. If there is a tie, any of the tied variables are acceptable
        return values.
        """
        candidates = set(self.crossword.variables) - set(assignment)
        # Initial random winner
        winner = candidates.pop()
        # Replace winner with better candidate
        for candidate in candidates:
            candidate_len = len(self.domains[candidate])
            winner_len = len(self.domains[winner])
            if candidate_len < winner_len:
                winner = candidate
            elif candidate_len == winner_len:
                # Compare neighbors count if tie with winner
                winner = max(winner,
                             candidate,
                             key=lambda x: len(self.crossword.neighbors(x)))
        return winner

    def backtrack(self, assignment):
        """
        Using Backtracking Search, take as input a partial assignment for the
        crossword and return a complete assignment if possible to do so.

        `assignment` is a mapping from variables (keys) to words (values).

        If no assignment is possible, return None.
        """
        # Base case
        if self.assignment_complete(assignment):
            return assignment
        # Recursion
        var = self.select_unassigned_variable(assignment)
        for word in self.order_domain_values(var, assignment):
            # Make action
            assignment[var] = word
            if self.consistent(assignment):
                result = self.backtrack(assignment)
                if result:
                    return result
            # Undo action
            assignment.pop(var)
        # No solution
        return None


def main():

    # Check usage
    if len(sys.argv) not in [3, 4]:
        sys.exit("Usage: python generate.py structure words [output]")

    # Parse command-line arguments
    structure = sys.argv[1]
    words = sys.argv[2]
    output = sys.argv[3] if len(sys.argv) == 4 else None

    # Generate crossword
    crossword = Crossword(structure, words)
    creator = CrosswordCreator(crossword)
    assignment = creator.solve()

    # Print result
    if assignment is None:
        print("No solution.")
    else:
        creator.print(assignment)
        if output:
            creator.save(assignment, output)


if __name__ == "__main__":
    main()
