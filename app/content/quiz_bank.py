"""Curated, hand-checked quiz questions.

When an OpenAI key is configured the Quiz Agent can generate extra questions too, but this bank
always works offline and gives reliable, auto-gradable questions.

Each question: key, category, topic_id, qtype, difficulty, prompt, options, answer, explanation,
option_explanations (why each option is right/wrong), code (optional), keywords (for "short").
For mcq/true_false/output/find_error, `answer` is the index of the correct option.
"""

from __future__ import annotations

QUESTIONS: list[dict] = []


def _add(key, cat, topic, qtype, diff, prompt, options, answer, explain, why=None, code=None, keywords=None):
    QUESTIONS.append(
        {
            "key": key,
            "category": cat,
            "topic_id": topic,
            "qtype": qtype,
            "difficulty": diff,
            "prompt": prompt,
            "code": code,
            "options": options,
            "answer": str(answer),
            "explanation": explain,
            "option_explanations": why or [],
            "keywords": keywords or [],
        }
    )


def mcq(key, cat, topic, diff, prompt, options, answer, explain, why=None, code=None, qtype="mcq"):
    _add(key, cat, topic, qtype, diff, prompt, options, answer, explain, why, code)


def tf(key, cat, topic, diff, prompt, is_true, explain):
    _add(key, cat, topic, "true_false", diff, prompt, ["True", "False"], 0 if is_true else 1, explain)


def short(key, cat, topic, diff, prompt, model_answer, keywords, explain):
    """Free-text answer. `keywords` is a list of groups; each group is 'alt1|alt2'."""
    _add(key, cat, topic, "short", diff, prompt, [], model_answer, explain, keywords=keywords)


# ============================================================ DSA Fundamentals
C = "dsa_fundamentals"
mcq("fund-01", C, "dsa.big_o", "easy", "What is the time complexity of accessing `arr[i]` in an array?",
    ["O(1)", "O(n)", "O(log n)", "O(n²)"], 0,
    "Arrays are stored contiguously, so the address of arr[i] is computed directly: base + i × size.",
    ["Correct — direct address calculation.", "That would be scanning every element.",
     "That's binary search, not direct access.", "No nested work is done."])
mcq("fund-02", C, "dsa.recursion", "medium", "What does this code print?",
    ["4", "10", "24", "0"], 1,
    "f(4) = 4 + f(3) = 4 + 3 + 2 + 1 + f(0) = 10. It sums 1..n.",
    ["That's just n.", "Correct: 4+3+2+1+0.", "That would be 4! (multiplication).", "Only the base case returns 0."],
    code="int f(int n) {\n    if (n == 0) return 0;\n    return n + f(n - 1);\n}\n// main:\ncout << f(4);", qtype="output")
tf("fund-03", C, "dsa.recursion", "easy",
   "A recursive function without a base case will eventually stop on its own.", False,
   "Without a base case the function keeps calling itself until the call stack overflows (stack overflow / RecursionError).")
mcq("fund-04", C, "dsa.big_o", "medium", "What is the time complexity of this loop?",
    ["O(n)", "O(log n)", "O(n log n)", "O(√n)"], 1,
    "i doubles each time (1, 2, 4, 8 …), so the loop runs about log₂(n) times.",
    ["It would be O(n) if i increased by 1.", "Correct — i doubles each step.",
     "There's no inner O(n) loop.", "That would need i*i < n as the condition."],
    code="for (int i = 1; i < n; i *= 2) {\n    cout << i;\n}")
mcq("fund-05", C, "dsa.complexity", "hard", "Merge sort follows T(n) = 2T(n/2) + n. What does this solve to?",
    ["O(n)", "O(n log n)", "O(n²)", "O(log n)"], 1,
    "There are log n levels of splitting and each level does O(n) merging work → O(n log n) (Master theorem case 2).",
    ["Ignores the log n levels.", "Correct.", "Would need each level to do more work.", "Ignores the n work per level."])
mcq("fund-06", C, "dsa.loops_conditions", "easy", "What is wrong with this Python code?",
    ["Missing colon after range(1, 5)", "range cannot start at 1", "print needs a semicolon", "i must be declared first"], 0,
    "Python needs a colon at the end of for/if/while/def lines: `for i in range(1, 5):`",
    ["Correct.", "range(start, stop) can start anywhere.", "Python doesn't use semicolons.",
     "Python variables don't need declarations."],
    code="for i in range(1, 5)\n    print(i)", qtype="find_error")
short("fund-07", C, "dsa.big_o", "medium", "In one or two lines: why do we drop constants in Big O (e.g. O(2n) → O(n))?",
      "Big O describes how running time grows as the input becomes very large; constant factors don't change the growth rate.",
      ["grow|growth|rate|scale|scales", "large|input size|big input|n increases|n grows|infinity"],
      "Big O is about the *shape* of growth for large n. 2n and n both grow linearly — doubling n doubles the time.")
mcq("fund-08", C, "dsa.backtracking", "medium", "How many subsets does a set of n distinct elements have?",
    ["n", "n²", "2ⁿ", "n!"], 2,
    "Each element is either in or out of a subset: 2 × 2 × … (n times) = 2ⁿ. That's why subset backtracking is O(2ⁿ).",
    ["Too few — that's only single-element subsets.", "Polynomial, too small.", "Correct.",
     "n! counts orderings (permutations), not subsets."])

# ============================================================ Arrays and Strings
C = "arrays_strings"
mcq("arr-01", C, "dsa.arrays", "easy", "In a 0-indexed array of size n, what is the index of the last element?",
    ["n", "n - 1", "n + 1", "1"], 1, "Indices go from 0 to n-1, so the last one is n-1.",
    ["Accessing index n is out of bounds!", "Correct.", "Further out of bounds.", "That's the second element."])
mcq("arr-02", C, "dsa.strings", "easy", "What does this Python code print?",
    ["hello", "olleh", "h", "Error"], 1, "s[::-1] slices the whole string with step -1, i.e. reversed.",
    code='s = "hello"\nprint(s[::-1])', qtype="output")
mcq("arr-03", C, "dsa.two_pointers", "medium",
    "Using two pointers (one at each end) to find a pair with a given sum in a *sorted* array takes:",
    ["O(n²)", "O(n log n)", "O(n)", "O(1)"], 2,
    "Each step moves one pointer inward, so at most n steps in total.",
    ["That's the brute-force nested loop.", "That would include sorting; the array is already sorted.", "Correct.",
     "We still need to look at elements."])
mcq("arr-04", C, "dsa.sliding_window", "medium",
    "Finding the maximum sum of any subarray of size k with a sliding window takes:",
    ["O(n·k)", "O(n)", "O(k)", "O(n²)"], 1,
    "Add the new element, subtract the one leaving the window: O(1) per step, n steps.",
    ["That's recomputing every window from scratch.", "Correct.", "We must scan all n elements.", "Too slow."])
mcq("arr-05", C, "dsa.prefix_sum", "medium",
    "arr = [2, 3, 4, 5] has prefix array pre = [0, 2, 5, 9, 14]. What is sum(arr[1..3]) using pre[r+1] - pre[l]?",
    ["12", "9", "14", "7"], 0, "pre[4] - pre[1] = 14 - 2 = 12, which is 3 + 4 + 5.",
    ["Correct.", "That's pre[3], the sum of arr[0..2].", "That's the total sum.", "That's 3 + 4 only."])
tf("arr-06", C, "dsa.hash_map", "easy", "Looking up a key in a hash map takes O(1) time on average.", True,
   "The hash function jumps straight to the bucket. (Worst case can be O(n) with many collisions.)")
mcq("arr-07", C, "dsa.arrays", "medium", "What is the bug in this C++ code?",
    ["`i <= 5` reads arr[5], which is out of bounds", "Arrays can't be initialised with {}", "cout can't print ints",
     "The loop should start at 1"], 0,
    "Valid indices are 0..4. Use `i < 5`. Reading arr[5] is undefined behaviour.",
    code="int arr[5] = {1, 2, 3, 4, 5};\nfor (int i = 0; i <= 5; i++)\n    cout << arr[i];", qtype="find_error")
mcq("arr-08", C, "dsa.sliding_window", "hard",
    "What is the length of the longest substring without repeating characters in \"pwwkew\"?",
    ["2", "3", "4", "6"], 1, "\"wke\" has length 3. (\"pwke\" is a subsequence, not a substring.)",
    ["\"pw\" is valid but not the longest.", "Correct: \"wke\".", "\"pwke\" isn't contiguous.",
     "The string has repeats."], qtype="output")

# ============================================================ Linked Lists
C = "linked_lists"
mcq("ll-01", C, "dsa.linked_list", "easy", "Accessing the k-th element of a singly linked list takes:",
    ["O(1)", "O(n)", "O(log n)", "O(n²)"], 1,
    "There are no indices — you must follow next pointers from the head, one node at a time.",
    ["That's arrays.", "Correct.", "No halving is possible.", "Just one pass is needed."])
mcq("ll-02", C, "dsa.linked_list", "easy", "In a singly linked list, the `next` of the last node is:",
    ["The head", "NULL / nullptr / None", "Itself", "The previous node"], 1,
    "The last node marks the end of the list with a null pointer.",
    ["That's a circular list.", "Correct.", "That would create a self-loop.", "Singly lists have no back links."])
mcq("ll-03", C, "dsa.linked_list", "medium", "Which technique detects a cycle in a linked list using O(1) extra space?",
    ["Store visited nodes in a hash set", "Floyd's slow & fast pointers", "Sort the list", "Reverse the list"], 1,
    "A fast pointer (2 steps) eventually meets the slow pointer (1 step) if there's a cycle.",
    ["Works, but uses O(n) space.", "Correct — tortoise and hare.", "Doesn't detect cycles.",
     "Reversal can't reliably detect cycles and changes the list."])
tf("ll-04", C, "dsa.doubly_linked_list", "medium",
   "In a doubly linked list, deleting a node when you already have a pointer to it takes O(1).", True,
   "You can reach both neighbours via prev and next and relink them directly.")
mcq("ll-05", C, "dsa.linked_list", "medium", "Why does this reverse function break the list?",
    ["`curr.next` is overwritten before saving the next node", "It should return head", "prev should start as head",
     "The loop condition should be `curr.next`"], 0,
    "Save the next node first: `nxt = curr.next; curr.next = prev; prev = curr; curr = nxt`.",
    code="def reverse(head):\n    prev = None\n    curr = head\n    while curr:\n        curr.next = prev\n        prev = curr\n        curr = curr.next\n    return prev",
    qtype="find_error")
mcq("ll-06", C, "dsa.linked_list", "medium", "How do you find the middle of a linked list in one pass?",
    ["Count nodes, then walk n/2", "Slow pointer moves 1, fast moves 2; when fast ends, slow is in the middle",
     "Use binary search", "Reverse it first"], 1,
    "When the fast pointer has covered the whole list, the slow one has covered half.",
    ["That's two passes.", "Correct.", "No random access in linked lists.", "Unnecessary and costly."])
mcq("ll-07", C, "dsa.circular_linked_list", "hard",
    "In a circular singly linked list where you keep only a *tail* pointer, inserting at the beginning costs:",
    ["O(1)", "O(n)", "O(log n)", "Impossible"], 0,
    "tail->next is the head, so insert the new node after tail: new->next = tail->next; tail->next = new.")

# ============================================================ Stack and Queue
C = "stack_queue"
mcq("sq-01", C, "dsa.stack", "easy", "A stack follows which principle?",
    ["FIFO", "LIFO", "Random access", "Priority order"], 1, "Last In, First Out — like a stack of plates.",
    ["That's a queue.", "Correct.", "That's an array.", "That's a priority queue."])
mcq("sq-02", C, "dsa.stack", "easy",
    "push(1), push(2), push(3), pop(), push(4), pop(), pop(). Which values are popped, in order?",
    ["3, 4, 2", "3, 2, 1", "1, 2, 3", "4, 3, 2"], 0,
    "[1,2,3] → pop 3 → [1,2] → push 4 → [1,2,4] → pop 4 → pop 2.", qtype="output")
mcq("sq-03", C, "dsa.queue", "easy", "Breadth-First Search (BFS) uses which data structure?",
    ["Stack", "Queue", "Heap", "Hash map"], 1, "BFS processes nodes in the order they were discovered — FIFO.",
    ["Stacks give DFS.", "Correct.", "Heaps are for Dijkstra.", "Used for visited, not the order."])
mcq("sq-04", C, "dsa.stack", "medium", "Checking whether brackets like \"{[()]}\" are balanced is best done with a:",
    ["Queue", "Stack", "Sorted array", "Linked list traversal only"], 1,
    "Push opening brackets; each closing bracket must match the most recent unmatched opener — the stack top.")
tf("sq-05", C, "dsa.circular_queue", "medium",
   "In an array-based circular queue of size n, the rear index advances with rear = (rear + 1) % n.", True,
   "The modulo wraps the index back to 0 after n-1, reusing freed slots.")
mcq("sq-06", C, "dsa.queue", "medium", "A queue built from two stacks has a dequeue cost of:",
    ["O(n) every time", "O(1) amortised", "O(log n)", "O(n²)"], 1,
    "Elements move from the input stack to the output stack at most once each, so the average cost is O(1).")
mcq("sq-07", C, "dsa.queue", "medium", "What does this print?",
    ["[0, 2, 3, 4]", "[0, 1, 2, 3, 4]", "[1, 2, 3, 4]", "[2, 3, 4, 0]"], 0,
    "[1,2,3] → append 4 → [1,2,3,4] → popleft → [2,3,4] → appendleft 0 → [0,2,3,4].",
    code="from collections import deque\nq = deque([1, 2, 3])\nq.append(4)\nq.popleft()\nq.appendleft(0)\nprint(list(q))",
    qtype="output")

# ============================================================ Trees and Graphs
C = "trees_graphs"
mcq("tg-01", C, "dsa.bst", "easy", "An inorder traversal of a Binary Search Tree visits values in:",
    ["Random order", "Ascending (sorted) order", "Descending order", "Level order"], 1,
    "Inorder = left, node, right, and in a BST left < node < right.")
mcq("tg-02", C, "dsa.binary_tree", "medium", "What is the maximum number of nodes in a binary tree with 3 levels?",
    ["3", "6", "7", "8"], 2, "Levels hold 1 + 2 + 4 = 7 nodes (2ʰ − 1 for h levels).")
mcq("tg-03", C, "dsa.bfs_dfs", "medium", "On an unweighted graph, BFS from a source finds:",
    ["The shortest path (fewest edges) to every reachable node", "A topological order", "A minimum spanning tree",
     "Longest paths"], 0, "BFS explores level by level, so the first time it reaches a node uses the fewest edges.")
mcq("tg-04", C, "dsa.dijkstra", "hard", "Dijkstra's algorithm can give wrong answers when the graph has:",
    ["Cycles", "Negative edge weights", "More than 1000 nodes", "Undirected edges"], 1,
    "Dijkstra assumes a node's distance is final once popped; a later negative edge could reduce it. Use Bellman-Ford.",
    ["Cycles with non-negative weights are fine.", "Correct.", "Size doesn't matter.", "Works for undirected graphs."])
tf("tg-05", C, "dsa.topological_sort", "medium",
   "A topological ordering exists only for Directed Acyclic Graphs (DAGs).", True,
   "A cycle A→B→A means A must come before B and B before A — impossible.")
mcq("tg-06", C, "dsa.heap", "medium", "Inserting an element into a binary heap with n elements takes:",
    ["O(1)", "O(log n)", "O(n)", "O(n log n)"], 1, "The new element is 'sifted up' along one root-to-leaf path of height log n.")
mcq("tg-07", C, "dsa.binary_tree", "medium", "What is the preorder traversal of this tree?",
    ["1 2 4 5 3", "4 2 5 1 3", "4 5 2 3 1", "1 2 3 4 5"], 0,
    "Preorder = node, left, right: 1 → (2 → 4 → 5) → 3.",
    ["Correct.", "That's inorder.", "That's postorder.", "That's level order."],
    code="        1\n       / \\\n      2   3\n     / \\\n    4   5", qtype="output")
mcq("tg-08", C, "dsa.dsu", "hard", "Which two optimisations make Disjoint Set Union nearly O(1) per operation?",
    ["Path compression and union by rank/size", "Sorting and binary search", "Memoization and tabulation",
     "Hashing and chaining"], 0, "Together they give O(α(n)) amortised — the inverse Ackermann function, ≤ 4 in practice.")

# ============================================================ Sorting and Searching
C = "sorting_searching"
mcq("ss-01", C, "dsa.binary_search", "easy", "Binary search only works correctly on data that is:",
    ["Sorted", "Unique", "Stored in a linked list", "Small"], 0,
    "It discards half the range based on comparisons with the middle, which is only valid if the data is sorted.")
mcq("ss-02", C, "dsa.binary_search", "easy", "What is the time complexity of binary search?",
    ["O(n)", "O(log n)", "O(1)", "O(n log n)"], 1, "The range halves each step: n, n/2, n/4 … → log₂ n steps.")
mcq("ss-03", C, "dsa.merge_sort", "medium", "Worst-case time complexity of merge sort:",
    ["O(n²)", "O(n log n)", "O(n)", "O(log n)"], 1, "It always splits evenly, so worst case = average case = O(n log n).")
mcq("ss-04", C, "dsa.quick_sort", "medium", "When does quick sort hit its O(n²) worst case?",
    ["When the pivot is always the smallest or largest element", "When the array has duplicates only",
     "When n is even", "Never"], 0,
    "E.g. an already sorted array with the first element as pivot: partitions are size n-1 and 0 every time.")
tf("ss-05", C, "dsa.insertion_sort", "medium", "Insertion sort runs in about O(n) time on an already (or nearly) sorted array.", True,
   "Each element only moves a few positions, so the inner loop does almost nothing.")
mcq("ss-06", C, "dsa.merge_sort", "medium", "Which of these sorting algorithms is stable?",
    ["Selection sort", "Quick sort (typical)", "Merge sort", "Heap sort"], 2,
    "Stable = equal elements keep their original order. Merge sort takes from the left half first on ties.")
mcq("ss-07", C, "dsa.binary_search", "hard", "This binary search returns -1 for a = [5], x = 5. What's the fix?",
    ["Change the loop condition to `lo <= hi`", "Use mid = (lo + hi + 1) / 2", "Set lo = mid instead of mid + 1",
     "Return lo instead of -1"], 0,
    "With `lo < hi`, the loop never checks the last remaining element when lo == hi. (Tip: mid = lo + (hi - lo) / 2 avoids overflow.)",
    code="int lo = 0, hi = n - 1;\nwhile (lo < hi) {\n    int mid = (lo + hi) / 2;\n    if (a[mid] == x) return mid;\n    if (a[mid] < x) lo = mid + 1;\n    else hi = mid - 1;\n}\nreturn -1;",
    qtype="find_error")
mcq("ss-08", C, "dsa.bubble_sort", "easy", "What is the array after ONE pass of bubble sort on [5, 1, 4, 2]?",
    ["[1, 4, 2, 5]", "[1, 2, 4, 5]", "[1, 5, 4, 2]", "[4, 1, 2, 5]"], 0,
    "Swap 5↔1 → [1,5,4,2]; 5↔4 → [1,4,5,2]; 5↔2 → [1,4,2,5]. The largest value bubbles to the end.", qtype="output")

# ============================================================ Dynamic Programming
C = "dynamic_programming"
mcq("dp-01", C, "dsa.dynamic_programming", "easy", "Dynamic Programming is useful when a problem has:",
    ["Overlapping subproblems and optimal substructure", "Only sorted input", "No recursion", "Random data"], 0,
    "Overlapping subproblems → caching helps; optimal substructure → the best answer is built from best sub-answers.")
mcq("dp-02", C, "dsa.dynamic_programming", "medium", "What is the time complexity of Fibonacci(n) with memoization?",
    ["O(2ⁿ)", "O(n)", "O(n²)", "O(log n)"], 1,
    "Each fib(i) is computed once and then read from the cache — n distinct subproblems.",
    ["That's the naive recursion without memo.", "Correct.", "No nested loops are needed.",
     "Possible with matrix exponentiation, not plain memoization."])
mcq("dp-03", C, "dsa.dynamic_programming", "medium",
    "You can climb 1 or 2 steps at a time. How many distinct ways are there to climb 4 stairs?",
    ["4", "5", "6", "8"], 1, "ways(n) = ways(n-1) + ways(n-2): 1, 2, 3, 5 → 5 ways.", qtype="output")
mcq("dp-04", C, "dsa.kadane", "medium", "Maximum subarray sum of [-2, 1, -3, 4, -1, 2, 1, -5, 4] (Kadane's):",
    ["4", "5", "6", "7"], 2, "The subarray [4, -1, 2, 1] sums to 6.")
tf("dp-05", C, "dsa.dynamic_programming", "easy", "Memoization is top-down; tabulation is bottom-up.", True,
   "Memoization = recursion + cache. Tabulation = fill a table iteratively from the smallest subproblems.")
mcq("dp-06", C, "dsa.dynamic_programming", "hard", "0/1 Knapsack with n items and capacity W using DP takes:",
    ["O(n + W)", "O(n · W)", "O(2ⁿ)", "O(n log n)"], 1, "The DP table has n × W states, each filled in O(1).")
mcq("dp-07", C, "dsa.dynamic_programming", "hard",
    "What is the length of the Longest Common Subsequence of \"ABCBDAB\" and \"BDCABA\"?",
    ["3", "4", "5", "6"], 1, "One LCS is \"BCBA\" (length 4).", qtype="output")
short("dp-08", C, "dsa.dynamic_programming", "medium", "Explain the difference between memoization and tabulation.",
      "Memoization is top-down: recursion that caches results. Tabulation is bottom-up: iteratively fill a table from base cases.",
      ["top-down|top down|recursion|recursive|cache", "bottom-up|bottom up|iterative|table|loop"],
      "Both avoid recomputation; memoization only computes needed states, tabulation avoids recursion overhead.")

# ============================================================ C++
C = "cpp"
mcq("cpp-01", C, "cpp.variables_operators", "easy", "What does this print?", ["3.5", "3", "4", "Error"], 1,
    "Both operands are int, so / does integer division and drops the fraction.",
    code="int a = 7, b = 2;\ncout << a / b;", qtype="output")
mcq("cpp-02", C, "cpp.loops_functions", "easy", "Which function signature passes x by reference?",
    ["void f(int x)", "void f(int &x)", "void f(int *x)", "void f(const x)"], 1,
    "`int &x` makes x an alias of the caller's variable, so changes are visible outside.",
    ["Pass by value — a copy.", "Correct.", "That passes a pointer (an address), not a reference.", "Invalid syntax."])
mcq("cpp-03", C, "cpp.pointers_references", "medium", "What does this print?", ["10", "20", "Address of x", "Error"], 1,
    "p stores x's address; *p = 20 writes through the pointer into x.",
    code="int x = 10;\nint* p = &x;\n*p = 20;\ncout << x;", qtype="output")
mcq("cpp-04", C, "cpp.stl_containers", "medium", "Which STL container keeps its keys in sorted order?",
    ["unordered_map", "map", "vector", "stack"], 1,
    "std::map is a balanced BST (red-black tree): O(log n) operations, keys sorted.",
    ["Hash table — no order, O(1) average.", "Correct.", "Keeps insertion order unless you sort it.", "LIFO only."])
mcq("cpp-05", C, "cpp.stl", "medium", "What is the time complexity of std::sort?", ["O(n)", "O(n log n)", "O(n²)", "O(log n)"], 1,
    "std::sort (introsort) guarantees O(n log n).")
mcq("cpp-06", C, "cpp.syntax", "easy", "Why won't this compile?",
    ["Missing semicolon after `int n = 5`", "main must return void", "endl is not valid", "n * n is not allowed in cout"], 0,
    "Every C++ statement must end with ;.",
    code="#include <iostream>\nusing namespace std;\nint main() {\n    int n = 5\n    cout << n * n << endl;\n    return 0;\n}",
    qtype="find_error")
mcq("cpp-07", C, "cpp.competitive_programming", "hard", "What's the problem with this code?",
    ["Nothing, c = 10¹⁰", "a * b overflows because it is computed as int before being stored",
     "Compile error", "c is always 0"], 1,
    "The multiplication happens in int (max ≈ 2.1×10⁹). Fix: `long long c = 1LL * a * b;`",
    code="int a = 100000, b = 100000;\nlong long c = a * b;", qtype="find_error")
tf("cpp-08", C, "cpp.oop", "medium", "Virtual functions enable runtime polymorphism in C++.", True,
   "A base-class pointer calling a virtual function runs the derived class's override, chosen at runtime.")
mcq("cpp-09", C, "cpp.stl_containers", "medium", "What does this print?", ["2 4", "1 4", "3 3", "2 3"], 0,
    "After push_back: {3,1,2,5}; sorted: {1,2,3,5}. v[1] = 2 and size = 4.",
    code="vector<int> v = {3, 1, 2};\nv.push_back(5);\nsort(v.begin(), v.end());\ncout << v[1] << \" \" << v.size();",
    qtype="output")

# ============================================================ Python
C = "python"
mcq("py-01", C, "python.variables_types", "easy", "What does this print?",
    ["<class 'int'>", "<class 'float'>", "1", "Error"], 1, "In Python 3, `/` always returns a float (1.5).",
    code="print(type(3 / 2))", qtype="output")
mcq("py-02", C, "python.variables_types", "easy", "What does this print?", ["3 1", "3.5 1", "3 0", "4 1"], 0,
    "// is floor division (3) and % is the remainder (1).", code="print(7 // 2, 7 % 2)", qtype="output")
mcq("py-03", C, "python.collections", "easy", "Which of these is immutable?", ["list", "dict", "set", "tuple"], 3,
    "Tuples can't be changed after creation, which also makes them hashable (usable as dict keys).")
mcq("py-04", C, "python.functions", "medium", "What does this print?", ["[2]", "[1, 2]", "[1]", "Error"], 1,
    "Default arguments are created ONCE when the function is defined, so the same list is reused. Use `bucket=None`.",
    code="def add(item, bucket=[]):\n    bucket.append(item)\n    return bucket\n\nadd(1)\nprint(add(2))", qtype="output")
mcq("py-05", C, "python.collections", "medium", "What does this print?",
    ["[0, 4, 16]", "[0, 1, 4, 9, 16]", "[1, 9]", "[4, 16]"], 0,
    "Keep x in 0..4 where x is even (0, 2, 4) and square them.",
    code="print([x * x for x in range(5) if x % 2 == 0])", qtype="output")
mcq("py-06", C, "python.collections", "easy", "What happens here?",
    ["Prints 3", "IndexError: list index out of range", "Prints None", "Prints [1, 2, 3]"], 1,
    "Valid indices are 0, 1, 2. Use nums[-1] or nums[2] for the last element.",
    code="nums = [1, 2, 3]\nprint(nums[3])", qtype="find_error")
mcq("py-07", C, "python.exceptions", "medium", "When does a `finally` block run?",
    ["Only if an exception occurred", "Only if no exception occurred", "Always", "Never if there is a return"], 2,
    "finally runs whether or not an exception happens — even after a return — so it's used for cleanup.")
mcq("py-08", C, "python.collections", "medium", "What does this print?", ["3", "4", "Error", "None"], 1,
    "b = a doesn't copy the list; both names refer to the same object. Use a.copy() for a copy.",
    code="a = [1, 2, 3]\nb = a\nb.append(4)\nprint(len(a))", qtype="output")
mcq("py-09", C, "python.collections", "hard", "What does this print?",
    ["[[1, 0], [0, 0]]", "[[1, 0], [1, 0]]", "[[1, 1], [0, 0]]", "Error"], 1,
    "`[[0] * 2] * 2` creates two references to the SAME inner list. Use `[[0] * 2 for _ in range(2)]`.",
    code="x = [[0] * 2] * 2\nx[0][0] = 1\nprint(x)", qtype="output")

# ============================================================ NumPy and Pandas
C = "numpy_pandas"
mcq("np-01", C, "ml.numpy", "easy", "What does this print?", ["[1 2 3 1 2 3]", "[2 4 6]", "[3 4 5]", "Error"], 1,
    "NumPy applies arithmetic element-wise (vectorised). (A Python list * 2 would repeat the list instead.)",
    code="import numpy as np\nprint(np.array([1, 2, 3]) * 2)", qtype="output")
mcq("np-02", C, "ml.numpy", "easy", "What is np.zeros((3, 4)).shape?", ["(4, 3)", "(3, 4)", "12", "(3,)"], 1,
    "The tuple you pass is the shape: 3 rows, 4 columns.")
mcq("np-03", C, "ml.numpy", "medium", "What does this print?", ["(2,)", "(2, 2)", "(1, 2)", "Error"], 1,
    "Broadcasting stretches (2,1) and (2,) to a common (2,2) shape.",
    code="import numpy as np\na = np.array([[1], [2]])   # shape (2, 1)\nb = np.array([10, 20])     # shape (2,)\nprint((a + b).shape)",
    qtype="output")
mcq("np-04", C, "ml.pandas", "easy", "Which function loads a CSV file into a DataFrame?",
    ["pd.load_csv()", "pd.read_csv()", "pd.open()", "np.read_csv()"], 1, "pd.read_csv('file.csv') returns a DataFrame.")
mcq("np-05", C, "ml.pandas", "medium", "What does df.groupby(\"city\")[\"sales\"].mean() return?",
    ["Average sales for each city", "Total sales", "Number of cities", "The sales column sorted by city"], 0,
    "groupby splits rows by city, then mean() aggregates the sales column within each group.")
mcq("np-06", C, "ml.data_cleaning", "medium", "By default, what does df.dropna() do?",
    ["Fills missing values with 0", "Removes rows containing any missing value", "Removes columns with missing values",
     "Counts missing values"], 1, "Default axis=0 drops rows. Use axis=1 for columns, fillna() to fill instead.")
mcq("np-07", C, "ml.numpy", "medium", "What does this print?", ["2", "7", "12", "6"], 1,
    "reshape(2, 5) gives rows [0..4] and [5..9]; row 1, column 2 is 7.",
    code="import numpy as np\nprint(np.arange(10).reshape(2, 5)[1, 2])", qtype="output")
tf("np-08", C, "ml.pandas", "medium", "df.loc selects by labels, while df.iloc selects by integer positions.", True,
   "e.g. df.loc[5, 'age'] uses the index label 5; df.iloc[5, 2] means 6th row, 3rd column.")

# ============================================================ Supervised Learning
C = "supervised"
mcq("sup-01", C, "ml.linear_regression", "easy", "Linear regression predicts:",
    ["A category", "A continuous number", "Clusters", "Probabilities only"], 1,
    "e.g. a house price or a temperature — a real-valued output.")
mcq("sup-02", C, "ml.logistic_regression", "easy", "Despite its name, logistic regression is mainly used for:",
    ["Regression", "Classification", "Clustering", "Dimensionality reduction"], 1,
    "It outputs a probability via the sigmoid, which is thresholded (e.g. at 0.5) to pick a class.")
mcq("sup-03", C, "ml.logistic_regression", "medium", "The sigmoid function outputs values in which range?",
    ["(-1, 1)", "(0, 1)", "[0, ∞)", "Any real number"], 1, "σ(z) = 1 / (1 + e^(−z)), always strictly between 0 and 1.",
    ["That's tanh.", "Correct.", "That's ReLU.", "That's the raw linear score z."])
mcq("sup-04", C, "ml.knn", "medium", "K-Nearest Neighbors with k = 1 tends to:",
    ["Underfit", "Overfit (high variance)", "Always be optimal", "Ignore the training data"], 1,
    "Each prediction copies a single neighbour, so noise in the training data directly affects predictions.")
mcq("sup-05", C, "ml.random_forest", "medium", "How does a random forest reduce overfitting compared to one decision tree?",
    ["By using a single very deep tree", "By averaging many trees trained on random samples and feature subsets",
     "By removing all features", "By using linear models"], 1,
    "Bagging + random features make trees different; averaging their votes cancels out individual errors.")
tf("sup-06", C, "ml.decision_trees", "medium", "Decision trees require feature scaling (e.g. StandardScaler) to work well.", False,
   "Trees split on thresholds of one feature at a time, so the scale of features doesn't matter.")
mcq("sup-07", C, "ml.svm", "hard", "What does the kernel trick let an SVM do?",
    ["Train faster on huge datasets", "Learn non-linear decision boundaries without explicitly computing high-dimensional features",
     "Handle missing values", "Do clustering"], 1,
    "Kernels compute similarities as if data were mapped to a higher-dimensional space where it becomes linearly separable.")
mcq("sup-08", C, "ml.naive_bayes", "medium", "Why is Naive Bayes called \"naive\"?",
    ["It's a simple algorithm for beginners", "It assumes features are independent given the class",
     "It ignores the prior", "It uses only one feature"], 1,
    "That assumption is rarely exactly true, but it works surprisingly well — especially for text classification.")
mcq("sup-09", C, "ml.linear_regression", "easy", "A trained model is y = 2x + 3. What does it predict for x = 5?",
    ["10", "13", "16", "8"], 1, "y = 2 × 5 + 3 = 13.", qtype="output")

# ============================================================ Unsupervised Learning
C = "unsupervised"
mcq("uns-01", C, "ml.kmeans", "easy", "What must you choose before running K-Means?",
    ["The labels", "k, the number of clusters", "The learning rate", "The number of trees"], 1,
    "K-Means needs k up front. The elbow method or silhouette score help choose it.")
mcq("uns-02", C, "ml.pca", "medium", "PCA finds new axes (principal components) that capture:",
    ["The maximum variance in the data", "The class labels", "The minimum variance", "Clusters"], 0,
    "The first component is the direction along which the data is most spread out.")
mcq("uns-03", C, "ml.dbscan", "medium", "A key advantage of DBSCAN over K-Means is that it:",
    ["Always runs faster", "Finds arbitrarily shaped clusters and labels outliers as noise without needing k",
     "Needs labelled data", "Only works in 2D"], 1, "DBSCAN groups dense regions using eps and min_samples.")
tf("uns-04", C, "ml.unsupervised_intro", "easy", "Unsupervised learning requires labelled data.", False,
   "Unsupervised learning finds structure in *unlabelled* data.")
mcq("uns-05", C, "ml.kmeans", "medium", "The 'elbow method' is used to:",
    ["Choose k for K-Means", "Normalise features", "Split train and test data", "Pick a kernel"], 0,
    "Plot inertia vs k; the point where improvement sharply slows (the elbow) is a good k.")
mcq("uns-06", C, "ml.association_rules", "medium", "In association rules, confidence(A → B) equals:",
    ["support(A ∪ B) / support(A)", "support(A) / support(B)", "support(B)", "support(A) × support(B)"], 0,
    "Of the transactions containing A, the fraction that also contain B.")
mcq("uns-07", C, "ml.kmeans", "hard", "Why should you scale features before K-Means?",
    ["K-Means uses distances, so large-scale features would dominate", "It makes K-Means supervised",
     "Scaling picks k automatically", "It isn't needed"], 0,
    "Income in rupees (10⁵) would swamp age (10¹) in Euclidean distance unless both are scaled.")

# ============================================================ ML Algorithms / fundamentals / evaluation
C = "ml_algorithms"
mcq("mla-01", C, "ml.overfitting", "easy", "Which sign indicates overfitting?",
    ["High training accuracy, low test accuracy", "Low training and low test accuracy",
     "Equal training and test accuracy", "High test accuracy only"], 0,
    "The model memorised the training data but doesn't generalise.",
    ["Correct.", "That's underfitting.", "That's usually healthy.", "Unusual and suspicious, not overfitting."])
mcq("mla-02", C, "ml.train_test", "easy", "Why do we keep a separate test set?",
    ["To train faster", "To measure performance on data the model has never seen", "To get more training data",
     "Because sklearn requires it"], 1, "Testing on training data would hide overfitting.")
mcq("mla-03", C, "ml.precision_recall", "medium", "Precision is calculated as:",
    ["TP / (TP + FP)", "TP / (TP + FN)", "(TP + TN) / total", "TN / (TN + FP)"], 0,
    "Of everything predicted positive, how much really was positive.",
    ["Correct.", "That's recall.", "That's accuracy.", "That's specificity."])
mcq("mla-04", C, "ml.precision_recall", "medium", "TP = 8, FP = 2, FN = 4. What is the recall?",
    ["0.80", "0.67", "0.50", "0.33"], 1, "Recall = TP / (TP + FN) = 8 / 12 ≈ 0.67. (Precision would be 8/10 = 0.80.)",
    qtype="output")
mcq("mla-05", C, "ml.accuracy", "medium",
    "95% of transactions are not fraud. A model always predicts \"not fraud\". What is its accuracy?",
    ["5%", "50%", "95%", "100%"], 2,
    "95% accurate yet useless — it never catches fraud (recall 0). Use precision/recall/F1 on imbalanced data.")
mcq("mla-06", C, "ml.cross_validation_intro", "medium", "In 5-fold cross validation you:",
    ["Train one model on 5 copies of the data", "Train 5 models, each validated on a different fold",
     "Use 5% of the data for testing", "Repeat training 5 times on the same split"], 1,
    "Each fold is the validation set once; the 5 scores are averaged.")
mcq("mla-07", C, "ml.bias_variance", "medium", "A model with high bias is most likely:",
    ["Overfitting", "Underfitting", "Perfect", "Leaking data"], 1, "High bias = too simple to capture the pattern.")
tf("mla-08", C, "ml.grid_search", "medium", "GridSearchCV tries every combination of the hyperparameter values you list.", True,
   "That's why it gets slow quickly — RandomizedSearchCV samples combinations instead.")
mcq("mla-09", C, "ml.variance_std", "medium",
    "Data: [2, 4, 4, 4, 5, 5, 7, 9]. The mean is 5. What is the (population) standard deviation?",
    ["1", "2", "4", "5"], 1, "Squared deviations sum to 32; 32/8 = 4 (variance); √4 = 2.", qtype="output")
mcq("mla-10", C, "ml.feature_engineering", "hard", "Fitting a StandardScaler on the FULL dataset before the train/test split causes:",
    ["Data leakage", "Underfitting", "Faster training", "Nothing — it's best practice"], 0,
    "Test-set statistics leak into training. Fit the scaler on training data only (a Pipeline does this for you).")
mcq("mla-11", C, "ml.central_tendency", "easy", "For [3, 1, 100, 9, 5], which measure is more robust to the outlier 100?",
    ["Mean", "Median", "Both equally", "Neither"], 1,
    "Median = 5 (middle of 1,3,5,9,100). Mean = 23.6, dragged up by 100.")
mcq("mla-12", C, "ml.regression_metrics", "medium", "Why does MSE punish big errors more than MAE?",
    ["Errors are squared", "It divides by n", "It ignores small errors", "It uses absolute values"], 0,
    "An error of 10 contributes 100 to MSE but only 10 to MAE.")

# ============================================================ Deep Learning
C = "deep_learning"
mcq("dl-01", C, "ml.activation_functions", "easy", "ReLU(x) equals:", ["1 / (1 + e⁻ˣ)", "max(0, x)", "x²", "tanh(x)"], 1,
    "ReLU passes positive values unchanged and zeroes out negatives.",
    ["That's sigmoid.", "Correct.", "Not an activation function in practice.", "That's tanh."])
mcq("dl-02", C, "ml.activation_functions", "medium", "Why do neural networks need non-linear activation functions?",
    ["To make training faster", "Without them, stacked layers collapse into a single linear function",
     "To reduce memory", "To normalise inputs"], 1,
    "A composition of linear layers is still linear, so the network couldn't learn complex patterns.")
mcq("dl-03", C, "ml.gradient_descent", "medium", "What usually happens if the learning rate is far too high?",
    ["Training is slow but stable", "The loss oscillates or diverges", "The model always reaches the global minimum",
     "Nothing changes"], 1, "Steps overshoot the minimum, bouncing around or blowing up.")
mcq("dl-04", C, "ml.cnn", "medium", "Convolutional Neural Networks are especially good for:",
    ["Tabular data", "Images and other grid-like data", "Sorting numbers", "Association rules"], 1,
    "Convolution filters detect local patterns (edges, textures) wherever they appear.")
mcq("dl-05", C, "ml.lstm", "hard", "LSTMs were designed mainly to solve which problem of simple RNNs?",
    ["Too many parameters", "Vanishing gradients / forgetting long-range information", "Overfitting on images",
     "Slow inference"], 1, "Gates let LSTMs keep information across long sequences.")
mcq("dl-06", C, "ml.backpropagation", "medium", "Backpropagation computes gradients using:",
    ["The chain rule of calculus", "Random search", "Sorting", "The kernel trick"], 0,
    "Error derivatives flow backwards layer by layer, multiplying local derivatives.")
tf("dl-07", C, "ml.transformers", "medium",
   "Transformers process all tokens of a sequence in parallel using self-attention instead of step-by-step recurrence.", True,
   "This parallelism is a big reason transformers train efficiently on GPUs.")
mcq("dl-08", C, "ml.activation_functions", "medium", "A softmax output layer produces:",
    ["Values that sum to 1, interpreted as class probabilities", "Only 0s and 1s", "Negative numbers", "One raw score"], 0,
    "softmax(zᵢ) = e^zᵢ / Σe^zⱼ — used for multi-class classification.")
mcq("dl-09", C, "ml.gradient_descent", "hard", "w = 5, the gradient dL/dw = 2, learning rate = 0.1. What is w after one step?",
    ["5.2", "4.8", "3.0", "4.9"], 1, "w ← w − lr × gradient = 5 − 0.1 × 2 = 4.8.", qtype="output")


def by_key() -> dict[str, dict]:
    return {q["key"]: q for q in QUESTIONS}
