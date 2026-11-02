"""Interview-style coding problems with reference solutions.

`tests` are verified by the test suite (tests/unit/test_content.py) by running every Python
reference solution, so the solutions shown to students are known to be correct.
"""

from __future__ import annotations

PROBLEMS: list[dict] = [
    {
        "slug": "two-sum",
        "title": "Two Sum",
        "difficulty": "easy",
        "pattern": "Hashing",
        "topic_id": "dsa.hash_map",
        "statement": "Given an array of integers `nums` and an integer `target`, return the indices of the two numbers that add up to `target`. Exactly one solution exists and you may not use the same element twice.",
        "examples": "Input: nums = [2, 7, 11, 15], target = 9\nOutput: [0, 1]   (because 2 + 7 = 9)",
        "hints": [
            "Brute force: try every pair with two loops. What is its complexity?",
            "For each number x, which other number do you need? (target − x)",
            "Store numbers you've already seen in a hash map: value → index.",
        ],
        "key_insight": "While scanning, check if target − x was seen before using a hash map → one pass, O(n).",
        "function": "two_sum",
        "solution_python": """def two_sum(nums, target):
    seen = {}                      # value -> index
    for i, x in enumerate(nums):
        need = target - x
        if need in seen:           # O(1) average lookup
            return [seen[need], i]
        seen[x] = i
    return []""",
        "solution_cpp": """vector<int> twoSum(vector<int>& nums, int target) {
    unordered_map<int, int> seen;          // value -> index
    for (int i = 0; i < (int)nums.size(); i++) {
        int need = target - nums[i];
        if (seen.count(need)) return {seen[need], i};
        seen[nums[i]] = i;
    }
    return {};
}""",
        "time": "O(n)",
        "space": "O(n)",
        "tags": ["Amazon", "Google", "array", "hash map"],
        "tests": [(([2, 7, 11, 15], 9), [0, 1]), (([3, 2, 4], 6), [1, 2]), (([3, 3], 6), [0, 1])],
    },
    {
        "slug": "valid-parentheses",
        "title": "Valid Parentheses",
        "difficulty": "easy",
        "pattern": "Stack",
        "topic_id": "dsa.stack",
        "statement": "Given a string `s` containing just '(', ')', '{', '}', '[' and ']', decide if it is valid: every opening bracket is closed by the same type, in the correct order.",
        "examples": "Input: \"()[]{}\" → true\nInput: \"(]\" → false\nInput: \"{[]}\" → true",
        "hints": [
            "Which bracket must a ')' match? The most recent unmatched opener.",
            "'Most recent' = Last In First Out → a stack.",
            "At the end, the stack must be empty.",
        ],
        "key_insight": "Push openers; on a closer, the stack top must be its matching opener.",
        "function": "is_valid",
        "solution_python": """def is_valid(s):
    pairs = {')': '(', ']': '[', '}': '{'}
    stack = []
    for ch in s:
        if ch in pairs:                       # closing bracket
            if not stack or stack[-1] != pairs[ch]:
                return False
            stack.pop()
        else:                                 # opening bracket
            stack.append(ch)
    return not stack""",
        "solution_cpp": """bool isValid(string s) {
    stack<char> st;
    for (char ch : s) {
        if (ch == '(' || ch == '[' || ch == '{') { st.push(ch); continue; }
        if (st.empty()) return false;
        char top = st.top(); st.pop();
        if ((ch == ')' && top != '(') || (ch == ']' && top != '[') || (ch == '}' && top != '{'))
            return false;
    }
    return st.empty();
}""",
        "time": "O(n)",
        "space": "O(n)",
        "tags": ["Microsoft", "Amazon", "stack", "string"],
        "tests": [(("()[]{}",), True), (("(]",), False), (("{[]}",), True), (("((",), False), (("",), True)],
    },
    {
        "slug": "valid-palindrome",
        "title": "Valid Palindrome",
        "difficulty": "easy",
        "pattern": "Two Pointers",
        "topic_id": "dsa.two_pointers",
        "statement": "Return true if `s` reads the same forwards and backwards after lower-casing and removing all non-alphanumeric characters.",
        "examples": "Input: \"A man, a plan, a canal: Panama\" → true\nInput: \"race a car\" → false",
        "hints": [
            "Compare the first and last characters, then move inward.",
            "Skip characters that aren't letters or digits.",
            "Compare in lower case.",
        ],
        "key_insight": "Two pointers from both ends, skipping non-alphanumerics → O(n) time, O(1) space.",
        "function": "is_palindrome",
        "solution_python": """def is_palindrome(s):
    left, right = 0, len(s) - 1
    while left < right:
        if not s[left].isalnum():
            left += 1
        elif not s[right].isalnum():
            right -= 1
        elif s[left].lower() != s[right].lower():
            return False
        else:
            left += 1
            right -= 1
    return True""",
        "solution_cpp": """bool isPalindrome(string s) {
    int left = 0, right = (int)s.size() - 1;
    while (left < right) {
        if (!isalnum(s[left])) left++;
        else if (!isalnum(s[right])) right--;
        else if (tolower(s[left]) != tolower(s[right])) return false;
        else { left++; right--; }
    }
    return true;
}""",
        "time": "O(n)",
        "space": "O(1)",
        "tags": ["Facebook", "two pointers", "string"],
        "tests": [(("A man, a plan, a canal: Panama",), True), (("race a car",), False), ((" ",), True)],
    },
    {
        "slug": "binary-search",
        "title": "Binary Search",
        "difficulty": "easy",
        "pattern": "Binary Search",
        "topic_id": "dsa.binary_search",
        "statement": "Given a sorted array `nums` and a `target`, return the index of target, or -1 if it isn't present. Aim for O(log n).",
        "examples": "Input: nums = [-1, 0, 3, 5, 9, 12], target = 9 → 4\nInput: same nums, target = 2 → -1",
        "hints": [
            "Compare target with the middle element.",
            "If the middle is smaller, the answer can only be on the right half.",
            "Loop while lo <= hi so you also check a single remaining element.",
        ],
        "key_insight": "Halve the search range each step using the sorted order.",
        "function": "search",
        "solution_python": """def search(nums, target):
    lo, hi = 0, len(nums) - 1
    while lo <= hi:
        mid = lo + (hi - lo) // 2
        if nums[mid] == target:
            return mid
        if nums[mid] < target:
            lo = mid + 1
        else:
            hi = mid - 1
    return -1""",
        "solution_cpp": """int search(vector<int>& nums, int target) {
    int lo = 0, hi = (int)nums.size() - 1;
    while (lo <= hi) {
        int mid = lo + (hi - lo) / 2;      // avoids overflow
        if (nums[mid] == target) return mid;
        if (nums[mid] < target) lo = mid + 1;
        else hi = mid - 1;
    }
    return -1;
}""",
        "time": "O(log n)",
        "space": "O(1)",
        "tags": ["binary search", "array"],
        "tests": [(([-1, 0, 3, 5, 9, 12], 9), 4), (([-1, 0, 3, 5, 9, 12], 2), -1), (([5], 5), 0)],
    },
    {
        "slug": "climbing-stairs",
        "title": "Climbing Stairs",
        "difficulty": "easy",
        "pattern": "Dynamic Programming",
        "topic_id": "dsa.dynamic_programming",
        "statement": "You climb a staircase of `n` steps, taking 1 or 2 steps at a time. In how many distinct ways can you reach the top?",
        "examples": "Input: n = 2 → 2  (1+1, 2)\nInput: n = 3 → 3  (1+1+1, 1+2, 2+1)",
        "hints": [
            "To reach step n, your last move came from step n-1 or n-2.",
            "So ways(n) = ways(n-1) + ways(n-2). Looks familiar?",
            "You only need the previous two values — O(1) space.",
        ],
        "key_insight": "ways(n) = ways(n-1) + ways(n-2) — the Fibonacci recurrence, computed bottom-up.",
        "function": "climb_stairs",
        "solution_python": """def climb_stairs(n):
    if n <= 2:
        return n
    prev2, prev1 = 1, 2           # ways(1), ways(2)
    for _ in range(3, n + 1):
        prev2, prev1 = prev1, prev1 + prev2
    return prev1""",
        "solution_cpp": """int climbStairs(int n) {
    if (n <= 2) return n;
    int prev2 = 1, prev1 = 2;
    for (int i = 3; i <= n; i++) {
        int cur = prev1 + prev2;
        prev2 = prev1;
        prev1 = cur;
    }
    return prev1;
}""",
        "time": "O(n)",
        "space": "O(1)",
        "tags": ["Adobe", "dp"],
        "tests": [((2,), 2), ((3,), 3), ((5,), 8), ((1,), 1)],
    },
    {
        "slug": "reverse-linked-list",
        "title": "Reverse Linked List",
        "difficulty": "easy",
        "pattern": "Linked List",
        "topic_id": "dsa.linked_list",
        "statement": "Given the head of a singly linked list, reverse the list and return the new head.",
        "examples": "Input: 1 → 2 → 3 → 4 → 5\nOutput: 5 → 4 → 3 → 2 → 1",
        "hints": [
            "Walk the list once, flipping each node's next pointer.",
            "You need to remember the previous node.",
            "Save curr.next BEFORE overwriting it.",
        ],
        "key_insight": "Iteratively redirect each next pointer to the previous node using prev/curr/next.",
        "function": "reverse_list",
        "solution_python": """class ListNode:
    def __init__(self, val=0, next=None):
        self.val = val
        self.next = next

def reverse_list(head):
    prev, curr = None, head
    while curr:
        nxt = curr.next      # 1. save the rest of the list
        curr.next = prev     # 2. flip the pointer
        prev = curr          # 3. move prev forward
        curr = nxt           # 4. move curr forward
    return prev""",
        "solution_cpp": """ListNode* reverseList(ListNode* head) {
    ListNode* prev = nullptr;
    ListNode* curr = head;
    while (curr) {
        ListNode* nxt = curr->next;
        curr->next = prev;
        prev = curr;
        curr = nxt;
    }
    return prev;
}""",
        "time": "O(n)",
        "space": "O(1)",
        "tags": ["Microsoft", "linked list"],
        "tests": "linked_list",
    },
    {
        "slug": "maximum-subarray",
        "title": "Maximum Subarray",
        "difficulty": "medium",
        "pattern": "Kadane's Algorithm",
        "topic_id": "dsa.kadane",
        "statement": "Given an integer array `nums`, find the contiguous subarray (at least one element) with the largest sum and return the sum.",
        "examples": "Input: [-2, 1, -3, 4, -1, 2, 1, -5, 4] → 6   (subarray [4, -1, 2, 1])",
        "hints": [
            "Brute force checks all O(n²) subarrays.",
            "At each index, is it better to extend the previous subarray or start fresh here?",
            "best_ending_here = max(x, best_ending_here + x).",
        ],
        "key_insight": "Kadane: keep the best sum ending at each index; drop the prefix when it becomes negative.",
        "function": "max_subarray",
        "solution_python": """def max_subarray(nums):
    best = current = nums[0]
    for x in nums[1:]:
        current = max(x, current + x)   # extend or restart
        best = max(best, current)
    return best""",
        "solution_cpp": """int maxSubArray(vector<int>& nums) {
    int best = nums[0], current = nums[0];
    for (size_t i = 1; i < nums.size(); i++) {
        current = max(nums[i], current + nums[i]);
        best = max(best, current);
    }
    return best;
}""",
        "time": "O(n)",
        "space": "O(1)",
        "tags": ["Amazon", "LinkedIn", "dp", "array"],
        "tests": [(([-2, 1, -3, 4, -1, 2, 1, -5, 4],), 6), (([1],), 1), (([-3, -1, -2],), -1), (([5, 4, -1, 7, 8],), 23)],
    },
    {
        "slug": "longest-substring-without-repeating",
        "title": "Longest Substring Without Repeating Characters",
        "difficulty": "medium",
        "pattern": "Sliding Window",
        "topic_id": "dsa.sliding_window",
        "statement": "Given a string `s`, find the length of the longest substring without repeating characters.",
        "examples": "Input: \"abcabcbb\" → 3 (\"abc\")\nInput: \"pwwkew\" → 3 (\"wke\")",
        "hints": [
            "Keep a window [left, right] that has no duplicates.",
            "When s[right] is already in the window, move left past its previous position.",
            "Store the last index of each character in a hash map.",
        ],
        "key_insight": "Sliding window + last-seen index map: left jumps past duplicates, so each char is processed once.",
        "function": "length_of_longest_substring",
        "solution_python": """def length_of_longest_substring(s):
    last_seen = {}
    left = best = 0
    for right, ch in enumerate(s):
        if ch in last_seen and last_seen[ch] >= left:
            left = last_seen[ch] + 1      # shrink window past the duplicate
        last_seen[ch] = right
        best = max(best, right - left + 1)
    return best""",
        "solution_cpp": """int lengthOfLongestSubstring(string s) {
    unordered_map<char, int> lastSeen;
    int left = 0, best = 0;
    for (int right = 0; right < (int)s.size(); right++) {
        char ch = s[right];
        if (lastSeen.count(ch) && lastSeen[ch] >= left) left = lastSeen[ch] + 1;
        lastSeen[ch] = right;
        best = max(best, right - left + 1);
    }
    return best;
}""",
        "time": "O(n)",
        "space": "O(min(n, alphabet))",
        "tags": ["Amazon", "Bloomberg", "sliding window", "string"],
        "tests": [(("abcabcbb",), 3), (("bbbbb",), 1), (("pwwkew",), 3), (("",), 0), (("abba",), 2)],
    },
    {
        "slug": "number-of-islands",
        "title": "Number of Islands",
        "difficulty": "medium",
        "pattern": "BFS / DFS",
        "topic_id": "dsa.bfs_dfs",
        "statement": "Given a 2D grid of '1' (land) and '0' (water), count the islands. An island is land connected horizontally or vertically.",
        "examples": "Input:\n1 1 0 0\n1 0 0 1\n0 0 1 1\nOutput: 2",
        "hints": [
            "Each time you find unvisited land, you've found a new island.",
            "Then 'sink' the whole island with DFS/BFS so you don't count it again.",
            "Visit the 4 neighbours (up, down, left, right).",
        ],
        "key_insight": "Scan the grid; on each new '1', count it and flood-fill its connected land.",
        "function": "num_islands",
        "solution_python": """from collections import deque

def num_islands(grid):
    if not grid:
        return 0
    rows, cols = len(grid), len(grid[0])
    seen = set()
    islands = 0
    for r in range(rows):
        for c in range(cols):
            if grid[r][c] == '1' and (r, c) not in seen:
                islands += 1
                queue = deque([(r, c)])      # BFS flood fill
                seen.add((r, c))
                while queue:
                    x, y = queue.popleft()
                    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        nx, ny = x + dx, y + dy
                        if 0 <= nx < rows and 0 <= ny < cols and grid[nx][ny] == '1' and (nx, ny) not in seen:
                            seen.add((nx, ny))
                            queue.append((nx, ny))
    return islands""",
        "solution_cpp": """void sink(vector<vector<char>>& g, int r, int c) {
    if (r < 0 || c < 0 || r >= (int)g.size() || c >= (int)g[0].size() || g[r][c] != '1') return;
    g[r][c] = '0';                               // mark visited
    sink(g, r + 1, c); sink(g, r - 1, c); sink(g, r, c + 1); sink(g, r, c - 1);
}

int numIslands(vector<vector<char>>& grid) {
    int islands = 0;
    for (int r = 0; r < (int)grid.size(); r++)
        for (int c = 0; c < (int)grid[0].size(); c++)
            if (grid[r][c] == '1') { islands++; sink(grid, r, c); }
    return islands;
}""",
        "time": "O(rows × cols)",
        "space": "O(rows × cols)",
        "tags": ["Amazon", "Google", "graph", "bfs", "dfs"],
        "tests": [
            (([list("1100"), list("1001"), list("0011")],), 2),
            (([list("11110"), list("11010"), list("11000"), list("00000")],), 1),
            (([list("000")],), 0),
        ],
    },
    {
        "slug": "coin-change",
        "title": "Coin Change",
        "difficulty": "medium",
        "pattern": "Dynamic Programming",
        "topic_id": "dsa.dynamic_programming",
        "statement": "Given coin denominations `coins` and an `amount`, return the fewest coins needed to make the amount, or -1 if impossible. You have unlimited coins of each type.",
        "examples": "Input: coins = [1, 2, 5], amount = 11 → 3   (5 + 5 + 1)\nInput: coins = [2], amount = 3 → -1",
        "hints": [
            "Greedy (largest coin first) fails, e.g. coins [1, 3, 4], amount 6.",
            "Let dp[a] = fewest coins to make amount a.",
            "dp[a] = min(dp[a - coin] + 1) over all coins ≤ a.",
        ],
        "key_insight": "Bottom-up DP over amounts 0..amount, trying every coin as the last one used.",
        "function": "coin_change",
        "solution_python": """def coin_change(coins, amount):
    INF = float('inf')
    dp = [0] + [INF] * amount          # dp[a] = fewest coins for amount a
    for a in range(1, amount + 1):
        for coin in coins:
            if coin <= a and dp[a - coin] + 1 < dp[a]:
                dp[a] = dp[a - coin] + 1
    return dp[amount] if dp[amount] != INF else -1""",
        "solution_cpp": """int coinChange(vector<int>& coins, int amount) {
    const int INF = 1e9;
    vector<int> dp(amount + 1, INF);
    dp[0] = 0;
    for (int a = 1; a <= amount; a++)
        for (int coin : coins)
            if (coin <= a && dp[a - coin] != INF)
                dp[a] = min(dp[a], dp[a - coin] + 1);
    return dp[amount] == INF ? -1 : dp[amount];
}""",
        "time": "O(amount × number of coins)",
        "space": "O(amount)",
        "tags": ["Amazon", "Uber", "dp"],
        "tests": [(([1, 2, 5], 11), 3), (([2], 3), -1), (([1], 0), 0), (([1, 3, 4], 6), 2)],
    },
    {
        "slug": "kth-largest-element",
        "title": "Kth Largest Element in an Array",
        "difficulty": "medium",
        "pattern": "Heap",
        "topic_id": "dsa.heap",
        "statement": "Return the k-th largest element of `nums` (in sorted order, not the k-th distinct).",
        "examples": "Input: nums = [3, 2, 1, 5, 6, 4], k = 2 → 5",
        "hints": [
            "Sorting works in O(n log n). Can you do better when k is small?",
            "Keep only the k largest elements seen so far.",
            "A min-heap of size k: its top is the k-th largest.",
        ],
        "key_insight": "Maintain a size-k min-heap; pop whenever it grows past k → O(n log k).",
        "function": "find_kth_largest",
        "solution_python": """import heapq

def find_kth_largest(nums, k):
    heap = []
    for x in nums:
        heapq.heappush(heap, x)
        if len(heap) > k:
            heapq.heappop(heap)     # remove the smallest
    return heap[0]""",
        "solution_cpp": """int findKthLargest(vector<int>& nums, int k) {
    priority_queue<int, vector<int>, greater<int>> minHeap;
    for (int x : nums) {
        minHeap.push(x);
        if ((int)minHeap.size() > k) minHeap.pop();
    }
    return minHeap.top();
}""",
        "time": "O(n log k)",
        "space": "O(k)",
        "tags": ["Facebook", "heap", "priority queue"],
        "tests": [(([3, 2, 1, 5, 6, 4], 2), 5), (([3, 2, 3, 1, 2, 4, 5, 5, 6], 4), 4), (([1], 1), 1)],
    },
    {
        "slug": "merge-intervals",
        "title": "Merge Intervals",
        "difficulty": "medium",
        "pattern": "Sorting + Greedy",
        "topic_id": "dsa.greedy",
        "statement": "Given a list of intervals [start, end], merge all overlapping intervals and return the result.",
        "examples": "Input: [[1,3],[2,6],[8,10],[15,18]] → [[1,6],[8,10],[15,18]]",
        "hints": [
            "Overlaps are easy to spot once intervals are sorted by start.",
            "Compare each interval with the last merged one.",
            "If start ≤ last end, extend the end; otherwise start a new interval.",
        ],
        "key_insight": "Sort by start, then sweep once merging into the last interval.",
        "function": "merge",
        "solution_python": """def merge(intervals):
    intervals.sort(key=lambda iv: iv[0])
    merged = []
    for start, end in intervals:
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)   # overlap → extend
        else:
            merged.append([start, end])
    return merged""",
        "solution_cpp": """vector<vector<int>> merge(vector<vector<int>>& intervals) {
    sort(intervals.begin(), intervals.end());
    vector<vector<int>> merged;
    for (auto& iv : intervals) {
        if (!merged.empty() && iv[0] <= merged.back()[1])
            merged.back()[1] = max(merged.back()[1], iv[1]);
        else
            merged.push_back(iv);
    }
    return merged;
}""",
        "time": "O(n log n)",
        "space": "O(n)",
        "tags": ["Google", "Facebook", "sorting", "intervals"],
        "tests": [(([[1, 3], [2, 6], [8, 10], [15, 18]],), [[1, 6], [8, 10], [15, 18]]), (([[1, 4], [4, 5]],), [[1, 5]])],
    },
    {
        "slug": "course-schedule",
        "title": "Course Schedule",
        "difficulty": "medium",
        "pattern": "Topological Sort",
        "topic_id": "dsa.topological_sort",
        "statement": "There are `n` courses (0..n-1). `prereqs[i] = [a, b]` means you must take b before a. Can you finish all courses?",
        "examples": "Input: n = 2, prereqs = [[1, 0]] → true\nInput: n = 2, prereqs = [[1, 0], [0, 1]] → false (cycle)",
        "hints": [
            "Model courses as a directed graph.",
            "You can finish everything iff the graph has no cycle.",
            "Kahn's algorithm: repeatedly take courses with in-degree 0.",
        ],
        "key_insight": "Topological sort (Kahn's BFS); if you can't process all n nodes, there's a cycle.",
        "function": "can_finish",
        "solution_python": """from collections import deque

def can_finish(n, prereqs):
    graph = [[] for _ in range(n)]
    indegree = [0] * n
    for course, pre in prereqs:
        graph[pre].append(course)
        indegree[course] += 1
    queue = deque(i for i in range(n) if indegree[i] == 0)
    taken = 0
    while queue:
        node = queue.popleft()
        taken += 1
        for nxt in graph[node]:
            indegree[nxt] -= 1
            if indegree[nxt] == 0:
                queue.append(nxt)
    return taken == n""",
        "solution_cpp": """bool canFinish(int n, vector<vector<int>>& prereqs) {
    vector<vector<int>> graph(n);
    vector<int> indegree(n, 0);
    for (auto& p : prereqs) { graph[p[1]].push_back(p[0]); indegree[p[0]]++; }
    queue<int> q;
    for (int i = 0; i < n; i++) if (indegree[i] == 0) q.push(i);
    int taken = 0;
    while (!q.empty()) {
        int node = q.front(); q.pop(); taken++;
        for (int nxt : graph[node]) if (--indegree[nxt] == 0) q.push(nxt);
    }
    return taken == n;
}""",
        "time": "O(V + E)",
        "space": "O(V + E)",
        "tags": ["Amazon", "graph", "topological sort"],
        "tests": [((2, [[1, 0]]), True), ((2, [[1, 0], [0, 1]]), False), ((3, []), True)],
    },
    {
        "slug": "trapping-rain-water",
        "title": "Trapping Rain Water",
        "difficulty": "hard",
        "pattern": "Two Pointers",
        "topic_id": "dsa.two_pointers",
        "statement": "Given `height`, an elevation map where each bar has width 1, compute how much rain water it can trap.",
        "examples": "Input: [0,1,0,2,1,0,1,3,2,1,2,1] → 6",
        "hints": [
            "Water above bar i = min(max height to the left, max height to the right) − height[i].",
            "Prefix-max and suffix-max arrays give an O(n) time, O(n) space solution.",
            "Two pointers: the side with the smaller max decides the water level → O(1) space.",
        ],
        "key_insight": "Move the pointer with the smaller running max; water there = that max − height.",
        "function": "trap",
        "solution_python": """def trap(height):
    left, right = 0, len(height) - 1
    left_max = right_max = water = 0
    while left < right:
        if height[left] < height[right]:
            left_max = max(left_max, height[left])
            water += left_max - height[left]
            left += 1
        else:
            right_max = max(right_max, height[right])
            water += right_max - height[right]
            right -= 1
    return water""",
        "solution_cpp": """int trap(vector<int>& height) {
    int left = 0, right = (int)height.size() - 1;
    int leftMax = 0, rightMax = 0, water = 0;
    while (left < right) {
        if (height[left] < height[right]) {
            leftMax = max(leftMax, height[left]);
            water += leftMax - height[left++];
        } else {
            rightMax = max(rightMax, height[right]);
            water += rightMax - height[right--];
        }
    }
    return water;
}""",
        "time": "O(n)",
        "space": "O(1)",
        "tags": ["Google", "Amazon", "Goldman Sachs", "two pointers"],
        "tests": [(([0, 1, 0, 2, 1, 0, 1, 3, 2, 1, 2, 1],), 6), (([4, 2, 0, 3, 2, 5],), 9), (([],), 0)],
    },
]
