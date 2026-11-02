"""Hand-written lessons for flagship topics.

These are used when no LLM is configured (or the LLM call fails), so core topics always have a
complete, correct lesson. With an OpenAI key, every topic gets a freshly generated lesson that
follows the same structure (see app/llm/prompts.py).

Code outputs in these lessons are verified by tests/unit/test_content.py.
"""

from __future__ import annotations

LESSONS: dict[str, dict] = {
    # ------------------------------------------------------------------------------------------
    "dsa.big_o": {
        "intro": (
            "*Big O* tells you how the work an algorithm does *grows* when the input gets bigger.\n\n"
            "*Why it matters:* an O(n²) solution that is fine for 100 items can take hours for 1,000,000. "
            "Interviewers always ask for complexity.\n\n"
            "*Real-world analogy:* finding a name in a phone book\n"
            "• Reading every page → O(n)\n"
            "• Opening the middle and halving each time → O(log n)\n"
            "• Knowing the exact page number → O(1)"
        ),
        "diagram": (
            "*Growth for n = 1,000*\n```\n"
            "O(1)        1 step\n"
            "O(log n)    ~10 steps\n"
            "O(n)        1,000 steps\n"
            "O(n log n)  ~10,000 steps\n"
            "O(n²)       1,000,000 steps\n```\n"
            "*Rules:* drop constants (O(2n) → O(n)) and keep the biggest term (O(n² + n) → O(n²))."
        ),
        "code": {
            "cpp": "#include <iostream>\nusing namespace std;\n\nint main() {\n    int n = 4, steps = 0;\n    for (int i = 0; i < n; i++)        // runs n times\n        for (int j = 0; j < n; j++)    // runs n times for EACH i\n            steps++;\n    cout << steps << endl;             // n * n\n    return 0;\n}",
            "python": "n = 4\nsteps = 0\nfor i in range(n):          # runs n times\n    for j in range(n):      # runs n times for EACH i\n        steps += 1\nprint(steps)                # n * n",
        },
        "line_by_line": (
            "*Line by line*\n"
            "• `steps` counts how many times the innermost line runs.\n"
            "• The outer loop runs n times.\n"
            "• For every outer iteration, the inner loop runs n times.\n"
            "• Total = n × n = n² → *O(n²)*."
        ),
        "dry_run": "*Dry run (n = 4)*\ni=0 → 4 steps, i=1 → 4, i=2 → 4, i=3 → 4 → total *16*.",
        "output": "16",
        "complexity": "*Time:* O(n²)  •  *Space:* O(1) (only two counters)",
        "mistakes": (
            "*Common mistakes*\n"
            "• Thinking two loops *one after another* are O(n²) — they are O(n + n) = O(n).\n"
            "• Forgetting hidden loops: `x in list` in Python is O(n).\n"
            "• Confusing best case with worst case."
        ),
        "simpler": (
            "Let's make it super simple 🙂\n\n"
            "Imagine handing out sweets:\n"
            "• Giving 1 sweet to the class monitor → same effort for any class size → *O(1)*\n"
            "• Giving 1 sweet to every student → double the students, double the effort → *O(n)*\n"
            "• Every student shakes hands with every other student → effort explodes → *O(n²)*\n\n"
            "Big O just answers: *if the class doubles, how much more work do I do?*"
        ),
    },
    # ------------------------------------------------------------------------------------------
    "dsa.recursion": {
        "intro": (
            "*Recursion* is when a function solves a problem by calling *itself* on a smaller version of the same problem.\n\n"
            "Every recursive function needs:\n"
            "1. *Base case* — the smallest problem, answered directly (stops the recursion)\n"
            "2. *Recursive case* — break the problem into a smaller one and call yourself\n\n"
            "*Why it matters:* trees, graphs, backtracking and DP are all built on recursion.\n\n"
            "*Analogy:* Russian dolls 🪆 — open one, there's a smaller one inside, until the tiniest doll (base case)."
        ),
        "diagram": (
            "*Call stack for factorial(3)*\n```\n"
            "factorial(3) = 3 * factorial(2)\n"
            "                   factorial(2) = 2 * factorial(1)\n"
            "                                      factorial(1) = 1   ← base case\n"
            "                   factorial(2) = 2 * 1 = 2\n"
            "factorial(3) = 3 * 2 = 6\n```"
        ),
        "code": {
            "cpp": "#include <iostream>\nusing namespace std;\n\nint factorial(int n) {\n    if (n <= 1) return 1;          // base case\n    return n * factorial(n - 1);   // recursive case\n}\n\nint main() {\n    cout << factorial(5) << endl;\n    return 0;\n}",
            "python": "def factorial(n):\n    if n <= 1:                     # base case\n        return 1\n    return n * factorial(n - 1)    # recursive case\n\nprint(factorial(5))",
        },
        "line_by_line": (
            "*Line by line*\n"
            "• `if n <= 1: return 1` — the base case; without it the calls never stop.\n"
            "• `n * factorial(n - 1)` — trust that factorial(n-1) works, and build on it.\n"
            "• Each call waits on the *call stack* until the smaller call returns."
        ),
        "dry_run": "*Dry run*\nfactorial(5) = 5 × 4 × 3 × 2 × factorial(1) = 5 × 4 × 3 × 2 × 1 = *120*",
        "output": "120",
        "complexity": "*Time:* O(n) calls  •  *Space:* O(n) for the call stack",
        "mistakes": (
            "*Common mistakes*\n"
            "• Missing/incorrect base case → stack overflow (RecursionError in Python).\n"
            "• Not making the problem smaller (calling f(n) inside f(n)).\n"
            "• Forgetting to `return` the recursive result."
        ),
        "simpler": (
            "Simpler picture 🙂\n\n"
            "You're in a long queue and want to know your position. You ask the person in front: \"what's your position?\" "
            "They ask the person in front of them… until the first person says \"I'm 1!\" (base case). "
            "Then each person adds 1 and passes the answer back.\n\n"
            "That's recursion: *ask a smaller version, wait, then add your bit.*"
        ),
    },
    # ------------------------------------------------------------------------------------------
    "dsa.binary_search": {
        "intro": (
            "*Binary Search* finds a target in a *sorted* array by repeatedly checking the middle and throwing away half of the range.\n\n"
            "*Why it matters:* O(log n) — searching 1 billion items takes only ~30 steps!\n\n"
            "*Analogy:* guessing a number between 1 and 100. You say 50, hear \"higher\", then 75… you never check one by one."
        ),
        "diagram": (
            "*Search for 23*\n```\n"
            "index:  0  1  2   3   4   5   6\n"
            "array: [2, 5, 8, 12, 16, 23, 38]\n"
            "        lo        mid          hi   12 < 23 → go right\n"
            "                      lo  mid  hi   23 == 23 → found at 5\n```"
        ),
        "code": {
            "cpp": "#include <iostream>\n#include <vector>\nusing namespace std;\n\nint binarySearch(const vector<int>& a, int target) {\n    int lo = 0, hi = a.size() - 1;\n    while (lo <= hi) {\n        int mid = lo + (hi - lo) / 2;\n        if (a[mid] == target) return mid;\n        if (a[mid] < target) lo = mid + 1;\n        else hi = mid - 1;\n    }\n    return -1;\n}\n\nint main() {\n    vector<int> a = {2, 5, 8, 12, 16, 23, 38};\n    cout << binarySearch(a, 23) << endl;\n    return 0;\n}",
            "python": "def binary_search(a, target):\n    lo, hi = 0, len(a) - 1\n    while lo <= hi:\n        mid = lo + (hi - lo) // 2\n        if a[mid] == target:\n            return mid\n        if a[mid] < target:\n            lo = mid + 1\n        else:\n            hi = mid - 1\n    return -1\n\nprint(binary_search([2, 5, 8, 12, 16, 23, 38], 23))",
        },
        "line_by_line": (
            "*Line by line*\n"
            "• `lo, hi` — the range that could still contain the target.\n"
            "• `while lo <= hi` — keep going while the range is non-empty (`<=` so a single element is checked).\n"
            "• `mid = lo + (hi - lo) / 2` — middle index, written this way to avoid integer overflow in C++.\n"
            "• `a[mid] < target` → target is on the right → `lo = mid + 1`.\n"
            "• otherwise it's on the left → `hi = mid - 1`.\n"
            "• `return -1` — the range became empty, so the target isn't present."
        ),
        "dry_run": "*Dry run (target 23)*\nlo=0, hi=6 → mid=3 (12) < 23 → lo=4\nlo=4, hi=6 → mid=5 (23) == 23 → return *5*",
        "output": "5",
        "complexity": "*Time:* O(log n)  •  *Space:* O(1)",
        "mistakes": (
            "*Common mistakes*\n"
            "• Using it on unsorted data.\n"
            "• `while (lo < hi)` — misses the last element.\n"
            "• `lo = mid` instead of `mid + 1` → infinite loop.\n"
            "• `(lo + hi) / 2` overflowing for large ints in C++."
        ),
        "simpler": (
            "Simpler version 🙂\n\n"
            "Think of a dictionary. To find \"mango\" you don't read from page 1. You open the middle — it says \"L\". "
            "\"M\" comes after \"L\", so you ignore the whole first half. Open the middle of the remaining part… repeat.\n\n"
            "Each step cuts the pages in half. That's binary search!"
        ),
    },
    # ------------------------------------------------------------------------------------------
    "dsa.two_pointers": {
        "intro": (
            "*Two Pointers* uses two indices that move through the data — often one from each end — to replace a nested loop.\n\n"
            "*Why it matters:* turns many O(n²) brute-force solutions into O(n). Classic for sorted arrays, palindromes and pair sums.\n\n"
            "*Analogy:* two friends searching a row of lockers from opposite ends, walking towards each other."
        ),
        "diagram": (
            "*Pair with sum 10 in a sorted array*\n```\n"
            "[1, 3, 4, 6, 8, 11]\n"
            " L               R   1+11=12 > 10 → R--\n"
            " L            R      1+8=9  < 10 → L++\n"
            "    L         R      3+8=11 > 10 → R--\n"
            "    L      R         3+6=9  < 10 → L++\n"
            "       L   R         4+6=10 ✓\n```"
        ),
        "code": {
            "cpp": "#include <iostream>\n#include <vector>\nusing namespace std;\n\nint main() {\n    vector<int> a = {1, 3, 4, 6, 8, 11};\n    int target = 10;\n    int left = 0, right = a.size() - 1;\n    while (left < right) {\n        int sum = a[left] + a[right];\n        if (sum == target) {\n            cout << a[left] << \" + \" << a[right] << endl;\n            break;\n        }\n        if (sum < target) left++;   // need a bigger sum\n        else right--;               // need a smaller sum\n    }\n    return 0;\n}",
            "python": "a = [1, 3, 4, 6, 8, 11]\ntarget = 10\nleft, right = 0, len(a) - 1\nwhile left < right:\n    s = a[left] + a[right]\n    if s == target:\n        print(a[left], '+', a[right])\n        break\n    if s < target:\n        left += 1       # need a bigger sum\n    else:\n        right -= 1      # need a smaller sum",
        },
        "line_by_line": (
            "*Line by line*\n"
            "• `left` starts at the smallest value, `right` at the largest.\n"
            "• Sum too small → move `left` right (only way to increase it).\n"
            "• Sum too big → move `right` left (only way to decrease it).\n"
            "• Each step discards one element forever → at most n steps."
        ),
        "dry_run": "*Dry run:* see the diagram — 5 steps instead of checking all 15 pairs.",
        "output": "4 + 6",
        "complexity": "*Time:* O(n)  •  *Space:* O(1)",
        "mistakes": (
            "*Common mistakes*\n"
            "• Using it on an *unsorted* array for pair sums (sort first, or use a hash map).\n"
            "• `while (left <= right)` → pairs an element with itself.\n"
            "• Moving the wrong pointer."
        ),
        "simpler": (
            "Simpler version 🙂\n\n"
            "Students stand in a line sorted by height. You need two whose heights add to a target. "
            "Start with the shortest and the tallest. Too tall together? Swap the tallest for the next tallest. "
            "Too short? Swap the shortest for the next shortest. You walk inwards — never backwards."
        ),
    },
    # ------------------------------------------------------------------------------------------
    "dsa.sliding_window": {
        "intro": (
            "*Sliding Window* keeps a 'window' over a contiguous part of an array/string and slides it, updating the answer "
            "incrementally instead of recomputing everything.\n\n"
            "*Why it matters:* subarray/substring problems drop from O(n·k) or O(n²) to O(n).\n\n"
            "*Analogy:* looking out of a moving train window — one new tree enters, one old tree leaves."
        ),
        "diagram": (
            "*Max sum of 3 consecutive numbers*\n```\n"
            "[2, 1, 5, 1, 3, 2]\n"
            "[2  1  5] 1  3  2   sum = 8\n"
            " 2 [1  5  1] 3  2   8 - 2 + 1 = 7\n"
            " 2  1 [5  1  3] 2   7 - 1 + 3 = 9  ← best\n"
            " 2  1  5 [1  3  2]  9 - 5 + 2 = 6\n```"
        ),
        "code": {
            "cpp": "#include <iostream>\n#include <vector>\nusing namespace std;\n\nint main() {\n    vector<int> a = {2, 1, 5, 1, 3, 2};\n    int k = 3, window = 0;\n    for (int i = 0; i < k; i++) window += a[i];   // first window\n    int best = window;\n    for (int i = k; i < (int)a.size(); i++) {\n        window += a[i] - a[i - k];                 // slide: add new, remove old\n        best = max(best, window);\n    }\n    cout << best << endl;\n    return 0;\n}",
            "python": "a = [2, 1, 5, 1, 3, 2]\nk = 3\nwindow = sum(a[:k])            # first window\nbest = window\nfor i in range(k, len(a)):\n    window += a[i] - a[i - k]  # slide: add new, remove old\n    best = max(best, window)\nprint(best)",
        },
        "line_by_line": (
            "*Line by line*\n"
            "• Build the first window of size k.\n"
            "• For every next index i: add `a[i]` (entering) and subtract `a[i-k]` (leaving).\n"
            "• Track the best window sum seen so far."
        ),
        "dry_run": "*Dry run:* windows give 8 → 7 → 9 → 6, so the answer is *9*.",
        "output": "9",
        "complexity": "*Time:* O(n)  •  *Space:* O(1)",
        "mistakes": (
            "*Common mistakes*\n"
            "• Off-by-one when removing the element leaving the window (`a[i-k]`).\n"
            "• Using a fixed window when the problem needs a variable-size one (e.g. longest substring without repeats).\n"
            "• Recomputing `sum()` of the whole window every step (that's O(n·k) again)."
        ),
        "simpler": (
            "Simpler version 🙂\n\n"
            "You're tracking your marks for the *last 3 tests*. When a new test result comes in, you add it and forget the oldest one. "
            "You never re-add all three from scratch. That 'add new, drop old' trick is the sliding window."
        ),
    },
    # ------------------------------------------------------------------------------------------
    "dsa.linked_list": {
        "intro": (
            "A *Linked List* is a chain of nodes. Each node stores a *value* and a *pointer to the next node*. "
            "The last node points to NULL.\n\n"
            "*Why it matters:* O(1) insert/delete once you're at a node (no shifting like arrays). "
            "Used to build stacks, queues, LRU caches.\n\n"
            "*Analogy:* a treasure hunt 🗺️ — each clue tells you where the next clue is."
        ),
        "diagram": "```\nhead\n  ↓\n[10|•]→[20|•]→[30|•]→ NULL\n value next\n```\nArrays: elements side by side in memory.\nLinked list: nodes anywhere in memory, joined by pointers.",
        "code": {
            "cpp": "#include <iostream>\nusing namespace std;\n\nstruct Node {\n    int val;\n    Node* next;\n    Node(int v) : val(v), next(nullptr) {}\n};\n\nint main() {\n    Node* head = new Node(10);\n    head->next = new Node(20);\n    head->next->next = new Node(30);\n\n    for (Node* cur = head; cur != nullptr; cur = cur->next)\n        cout << cur->val << \" \";\n    cout << endl;\n    return 0;\n}",
            "python": "class Node:\n    def __init__(self, val):\n        self.val = val\n        self.next = None\n\nhead = Node(10)\nhead.next = Node(20)\nhead.next.next = Node(30)\n\ncur = head\nwhile cur:\n    print(cur.val, end=' ')\n    cur = cur.next",
        },
        "line_by_line": (
            "*Line by line*\n"
            "• `Node` holds `val` and `next` (initially empty).\n"
            "• We create 3 nodes and link them: 10 → 20 → 30.\n"
            "• Traversal: start at `head`, print, move to `cur.next`, stop at NULL/None."
        ),
        "dry_run": "*Dry run*\ncur=10 → print 10 → cur=20 → print 20 → cur=30 → print 30 → cur=NULL → stop",
        "output": "10 20 30",
        "complexity": "*Access by index:* O(n)  •  *Insert at head:* O(1)  •  *Space:* O(n)",
        "mistakes": (
            "*Common mistakes*\n"
            "• Losing the rest of the list by overwriting `next` before saving it.\n"
            "• Dereferencing NULL (check `cur != nullptr`).\n"
            "• Forgetting to update `head` when inserting/deleting at the front."
        ),
        "simpler": (
            "Simpler version 🙂\n\n"
            "Think of a train 🚂. Each coach is hooked to the next coach. To reach coach 5, you must walk through coaches 1–4 (O(n)). "
            "But adding a new coach right after the one you're standing in is easy — just change two hooks (O(1))."
        ),
    },
    # ------------------------------------------------------------------------------------------
    "dsa.stack": {
        "intro": (
            "A *Stack* is a Last-In-First-Out (LIFO) structure. You can only add (*push*) or remove (*pop*) from the *top*.\n\n"
            "*Why it matters:* undo buttons, browser back button, matching brackets, function calls (the call stack), DFS.\n\n"
            "*Analogy:* a stack of plates 🍽️ — you take the one you put on last."
        ),
        "diagram": "```\npush 1   push 2   push 3   pop → 3\n                   | 3 |\n          | 2 |    | 2 |    | 2 |\n| 1 |     | 1 |    | 1 |    | 1 |\n```",
        "code": {
            "cpp": "#include <iostream>\n#include <stack>\nusing namespace std;\n\nint main() {\n    stack<int> st;\n    st.push(1);\n    st.push(2);\n    st.push(3);\n    cout << st.top() << endl;  // 3\n    st.pop();                  // removes 3\n    cout << st.top() << endl;  // 2\n    cout << st.size() << endl; // 2\n    return 0;\n}",
            "python": "stack = []\nstack.append(1)      # push\nstack.append(2)\nstack.append(3)\nprint(stack[-1])     # top -> 3\nstack.pop()          # removes 3\nprint(stack[-1])     # 2\nprint(len(stack))    # 2",
        },
        "line_by_line": (
            "*Line by line*\n"
            "• push 1, 2, 3 → 3 is on top.\n"
            "• top/peek reads the top without removing it.\n"
            "• pop removes the top (3), so 2 becomes the top.\n"
            "• In Python, a list's end works as the stack top (append/pop are O(1))."
        ),
        "dry_run": "*Dry run*\n[] → [1] → [1,2] → [1,2,3] → top=3 → pop → [1,2] → top=2 → size=2",
        "output": "3\n2\n2",
        "complexity": "*push / pop / top:* O(1)  •  *Space:* O(n)",
        "mistakes": (
            "*Common mistakes*\n"
            "• Calling pop/top on an empty stack (check `empty()` first).\n"
            "• In C++, `pop()` returns nothing — read `top()` first.\n"
            "• Using `list.pop(0)` in Python (that's O(n) and gives queue behaviour)."
        ),
        "simpler": (
            "Simpler version 🙂\n\n"
            "Think of the *Ctrl+Z undo* button. Every action you do is placed on top of a pile. "
            "Undo removes the *most recent* action first. Last in, first out — that's a stack!"
        ),
    },
    # ------------------------------------------------------------------------------------------
    "ml.linear_regression": {
        "intro": (
            "*Linear Regression* predicts a number by fitting the best straight line through data: *y = w·x + b*.\n\n"
            "*Why it matters:* the simplest ML model, the foundation for neural networks, and great for predicting prices, marks, sales.\n\n"
            "*Real-world example:* predicting exam marks from hours studied. More hours → higher marks, roughly in a line."
        ),
        "diagram": (
            "*Mathematical intuition*\n"
            "• w (slope) = how much y changes when x increases by 1\n"
            "• b (intercept) = value of y when x = 0\n"
            "• We choose w, b to minimise the *Mean Squared Error*: average of (actual − predicted)²\n"
            "```\nmarks\n 90|            •\n 70|        • /\n 50|     •  /\n 30|  •  /\n   +----------- hours\n     1  2  3  4\n```"
        ),
        "code": {
            "python": "import numpy as np\nfrom sklearn.linear_model import LinearRegression\n\n# Dataset: hours studied -> marks\nhours = np.array([[1], [2], [3], [4], [5]])\nmarks = np.array([35, 45, 55, 65, 75])\n\nmodel = LinearRegression()\nmodel.fit(hours, marks)\n\nprint('slope w =', round(model.coef_[0], 2))\nprint('intercept b =', round(model.intercept_, 2))\nprint('prediction for 6 hours =', round(model.predict([[6]])[0], 2))",
        },
        "line_by_line": (
            "*Line by line*\n"
            "• `hours` is a 2D array (samples × features) — sklearn always expects 2D X.\n"
            "• `marks` is the label y we want to predict.\n"
            "• `LinearRegression()` creates the model; `fit` finds the best w and b.\n"
            "• `coef_` is w, `intercept_` is b.\n"
            "• `predict([[6]])` applies y = w·6 + b."
        ),
        "dry_run": "*Dataset:* every extra hour adds exactly 10 marks, starting at 25 → y = 10x + 25.\nFor 6 hours: 10 × 6 + 25 = *85*.",
        "output": "slope w = 10.0\nintercept b = 25.0\nprediction for 6 hours = 85.0",
        "complexity": "*Practice assignment:* use the Student Performance idea — create 10 rows of (hours, attendance) → marks, fit a *multiple* linear regression and print the coefficients. Which feature matters more?",
        "mistakes": (
            "*Common mistakes*\n"
            "• Passing a 1D X (use `X.reshape(-1, 1)`).\n"
            "• Using it for categories (use logistic regression for classification).\n"
            "• Evaluating on training data only — always keep a test set.\n"
            "• Extrapolating far outside the data range."
        ),
        "simpler": (
            "Simpler version 🙂\n\n"
            "A taxi charges ₹25 to start plus ₹10 per km. Fare = 10 × km + 25. That's a straight line!\n\n"
            "Linear regression is just the computer *discovering* the \"₹10 per km\" (slope) and \"₹25 start\" (intercept) "
            "by looking at many past rides."
        ),
    },
    # ------------------------------------------------------------------------------------------
    "ml.overfitting": {
        "intro": (
            "*Overfitting:* the model memorises the training data (including noise) and performs badly on new data.\n"
            "*Underfitting:* the model is too simple to capture the pattern, so it's bad everywhere.\n\n"
            "*Why it matters:* the goal of ML is to work on *unseen* data, not to ace the training set.\n\n"
            "*Real-world example:* a student who memorises last year's answers (overfits) fails when questions change; "
            "a student who studied nothing (underfits) fails both."
        ),
        "diagram": (
            "*Mathematical intuition — compare train vs test scores*\n```\n"
            "                 train   test\n"
            "Underfitting      low     low\n"
            "Good fit          high    high\n"
            "Overfitting      ~100%    low\n```\n"
            "*Fixes for overfitting:* more data, simpler model, regularisation, cross-validation, early stopping."
        ),
        "code": {
            "python": "import numpy as np\nfrom sklearn.tree import DecisionTreeRegressor\nfrom sklearn.model_selection import train_test_split\n\nrng = np.random.RandomState(0)\nX = np.sort(rng.rand(80, 1) * 5, axis=0)\ny = np.sin(X).ravel() + rng.normal(0, 0.2, 80)   # pattern + noise\n\nX_tr, X_te, y_tr, y_te = train_test_split(X, y, random_state=0)\n\nfor depth in [1, 3, None]:   # None = grow until it memorises\n    m = DecisionTreeRegressor(max_depth=depth, random_state=0).fit(X_tr, y_tr)\n    print(depth, round(m.score(X_tr, y_tr), 2), round(m.score(X_te, y_te), 2))",
        },
        "line_by_line": (
            "*Line by line*\n"
            "• We create data from sin(x) plus random noise.\n"
            "• Split into train and test sets.\n"
            "• Train trees with depth 1 (too simple), 3 (balanced) and unlimited (memorises).\n"
            "• `score` prints R² on train and test (1.0 = perfect)."
        ),
        "dry_run": (
            "*What to look for in the output (depth, train R², test R²)*\n"
            "• depth 1 → 0.70 / 0.70 → lowest scores on both → *underfitting*\n"
            "• depth 3 → 0.89 / 0.88 → high and close together → *good fit*\n"
            "• depth None → 1.00 / 0.86 → perfect on train, worse on test → *overfitting*"
        ),
        "output": "1 0.7 0.7\n3 0.89 0.88\nNone 1.0 0.86",
        "output_note": "(scikit-learn 1.x; tiny differences between versions are normal)",
        "complexity": "*Practice assignment:* repeat the experiment with depths 1–10, plot train and test R² against depth, and find the depth where the test score peaks.",
        "mistakes": (
            "*Common mistakes*\n"
            "• Judging a model by training accuracy.\n"
            "• Tuning hyperparameters on the test set (use a validation set / cross-validation).\n"
            "• Adding more features blindly."
        ),
        "simpler": (
            "Simpler version 🙂\n\n"
            "Overfitting = learning the answers. Underfitting = learning nothing. Good fit = learning the *method*.\n\n"
            "A good model, like a good student, can solve questions it has never seen before."
        ),
    },
    # ------------------------------------------------------------------------------------------
    "ml.numpy": {
        "intro": (
            "*NumPy* gives Python fast n-dimensional arrays and vectorised maths — the foundation of Pandas, scikit-learn and PyTorch.\n\n"
            "*Why it matters:* NumPy operations run in optimised C, often 10–100× faster than Python loops.\n\n"
            "*Real-world example:* an image is just a NumPy array of pixel values (height × width × 3 colours)."
        ),
        "diagram": (
            "*Mathematical intuition — shapes*\n```\n"
            "np.array([1, 2, 3])        shape (3,)    → vector\n"
            "np.array([[1, 2, 3],\n"
            "          [4, 5, 6]])      shape (2, 3)  → matrix\n```\n"
            "*Broadcasting:* (2, 3) + (3,) works — the row is 'stretched' over both rows."
        ),
        "code": {
            "python": "import numpy as np\n\nmarks = np.array([[78, 85, 90],\n                  [66, 72, 80]])   # 2 students x 3 subjects\n\nprint(marks.shape)\nprint(marks.mean(axis=1))        # average per student\nprint(marks + 5)                 # grace marks for everyone\nprint(marks[marks > 80])         # boolean filtering",
        },
        "line_by_line": (
            "*Line by line*\n"
            "• A 2×3 array: rows = students, columns = subjects.\n"
            "• `.shape` → (2, 3).\n"
            "• `mean(axis=1)` averages across columns, i.e. per student.\n"
            "• `marks + 5` adds 5 to every element (broadcasting — no loop).\n"
            "• `marks[marks > 80]` keeps only values above 80."
        ),
        "dry_run": "*Dataset:* student 1 = [78, 85, 90] → mean 84.33; student 2 = [66, 72, 80] → mean 72.67.",
        "output": "(2, 3)\n[84.33333333 72.66666667]\n[[83 90 95]\n [71 77 85]]\n[85 90]",
        "complexity": "*Practice assignment:* create a 5×4 array of random marks (np.random.randint), find each subject's highest mark (axis=0) and the number of students scoring above 75 overall.",
        "mistakes": (
            "*Common mistakes*\n"
            "• Confusing axis=0 (down columns) and axis=1 (across rows).\n"
            "• Using Python loops instead of vectorised operations.\n"
            "• Shape mismatches when broadcasting — print `.shape` often!"
        ),
        "simpler": (
            "Simpler version 🙂\n\n"
            "A NumPy array is like an Excel sheet that can do maths on the *whole sheet at once*. "
            "\"Add 5 to every cell\" is one command — no need to visit cells one by one."
        ),
    },
}


def get_lesson(topic_id: str) -> dict | None:
    return LESSONS.get(topic_id)
