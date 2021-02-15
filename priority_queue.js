// --------------
// Priority Queue
// --------------
const pq_parent = i => ((i + 1) >>> 1) - 1;
const pq_left = i => (i << 1) + 1;
const pq_right = i => (i + 1) << 1;
class PriorityQueue {
    constructor(comparator) {
        this._heap = [];
        this._comparator = comparator;
    }

    size() {
        return this._heap.length;
    }

    peek() {
        return this._heap[0];
    }

    push(value) {
        this._heap.push(value);
        this._siftUp();
    }

    pop() {
        const poppedValue = this.peek();
        const bottom = this.size() - 1;
        if (bottom > 0) {
            this._swap(0, bottom);
        }
        this._heap.pop();
        this._siftDown();
        return poppedValue;
    }

    _greater(i, j) { // greater means higher-priority
        return this._comparator(this._heap[i], this._heap[j]);
    }

    _swap(i, j) {
        [this._heap[i], this._heap[j]] = [this._heap[j], this._heap[i]];
    }

    _siftUp() {
        let node = this.size() - 1;
        while (node > 0 && this._greater(node, pq_parent(node))) {
            this._swap(node, pq_parent(node));
            node = pq_parent(node);
        }
    }

    _siftDown() {
        let node = 0;
        while (
            (pq_left(node) < this.size() && this._greater(pq_left(node), node)) ||
            (pq_right(node) < this.size() && this._greater(pq_right(node), node))
        ) {
            let maxChild = (pq_right(node) < this.size() && this._greater(pq_right(node), pq_left(node))) ? pq_right(node) : pq_left(node);
            this._swap(node, maxChild);
            node = maxChild;
        }
    }
}
