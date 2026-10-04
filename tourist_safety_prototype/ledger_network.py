"""
ledger_network.py - Simulated PERMISSIONED blockchain network.

N validator nodes each hold a full copy of the hash-chained ledger. A new block is committed
only if a MAJORITY of nodes validate it (hash, link to previous block, proof-of-work).
Tampering with one node's copy is detected by comparing it with the majority and can be
healed by re-syncing from the majority.  Honest limits: nodes run in one process and there is
no network/Byzantine fault tolerance protocol - this is a teaching simulation of consensus.
"""
import copy
import hashlib
import config as C


def sha256(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def block_hash_of(b):
    return sha256(f"{b['index_no']}|{b['payload_hash']}|{b['previous_hash']}|{b['timestamp']}|{b['nonce']}")


def mine(index_no, tourist_id, payload_hash, previous_hash, timestamp):
    """Proof-of-work: find nonce so block hash starts with POW_DIFFICULTY zeros."""
    prefix = "0" * C.POW_DIFFICULTY
    nonce = 0
    b = {"index_no": index_no, "tourist_id": tourist_id, "payload_hash": payload_hash,
         "previous_hash": previous_hash, "timestamp": timestamp, "nonce": 0}
    while True:
        b["nonce"] = nonce
        h = block_hash_of(b)
        if h.startswith(prefix):
            b["block_hash"] = h
            return b
        nonce += 1


def validate_block(b, prev):
    """Stateless validation used by every node: hash, PoW, link to previous block."""
    if block_hash_of(b) != b["block_hash"]:
        return False, "block hash mismatch"
    if not b["block_hash"].startswith("0" * C.POW_DIFFICULTY) and b["index_no"] != 0:
        return False, "proof-of-work invalid"
    if prev is None:
        return (b["previous_hash"] == "0" * 64), "genesis link"
    if b["index_no"] != prev["index_no"] + 1:
        return False, "index not sequential"
    if b["previous_hash"] != prev["block_hash"]:
        return False, "previous-hash link broken"
    return True, "ok"


def genesis_block():
    b = {"index_no": 0, "tourist_id": "GENESIS", "payload_hash": sha256("genesis"),
         "previous_hash": "0" * 64, "timestamp": "2026-01-01T00:00:00+00:00", "nonce": 0}
    b["block_hash"] = block_hash_of(b)
    return b


class Node:
    def __init__(self, name):
        self.name = name
        self.chain = []

    def first_bad_index(self):
        prev = None
        for b in self.chain:
            ok, _ = validate_block(b, prev)
            if not ok:
                return b["index_no"]
            prev = b
        return None

    def head(self):
        return self.chain[-1] if self.chain else None


class LedgerNetwork:
    def __init__(self, n_nodes=None):
        self.nodes = [Node(f"Node-{i + 1}") for i in range(n_nodes or C.NUM_LEDGER_NODES)]
        self.majority = len(self.nodes) // 2 + 1

    def load(self, blocks):
        for n in self.nodes:
            n.chain = copy.deepcopy(blocks)

    def propose(self, block):
        votes = 0
        for n in self.nodes:
            if n.first_bad_index() is not None:
                continue                       # a corrupted node cannot vote
            ok, _ = validate_block(block, n.head())
            votes += 1 if ok else 0
        if votes < self.majority:
            raise ValueError(f"block rejected: only {votes}/{len(self.nodes)} validators approved")
        for n in self.nodes:
            if n.first_bad_index() is None:
                n.chain.append(copy.deepcopy(block))
        return votes

    def consensus(self, index_no, block_hash):
        """How many healthy nodes hold exactly this block at this index?"""
        agree = 0
        for n in self.nodes:
            if n.first_bad_index() is None and index_no < len(n.chain) \
                    and n.chain[index_no]["block_hash"] == block_hash:
                agree += 1
        return {"agree": agree, "total": len(self.nodes), "ok": agree >= self.majority}

    def status(self):
        heads = {}
        for n in self.nodes:
            h = n.head()["block_hash"] if n.head() and n.first_bad_index() is None else None
            heads[n.name] = h
        counts = {}
        for h in heads.values():
            if h:
                counts[h] = counts.get(h, 0) + 1
        maj_head = max(counts, key=counts.get) if counts else None
        out = []
        for n in self.nodes:
            bad = n.first_bad_index()
            h = heads[n.name]
            if bad is not None:
                state, detail = "TAMPERED", f"invalid block at index {bad}"
            elif h != maj_head:
                state, detail = "DIVERGED", "head differs from majority"
            else:
                state, detail = "OK", "in sync"
            out.append({"name": n.name, "blocks": len(n.chain), "state": state, "detail": detail,
                        "head": (h or "")[:12]})
        healthy = sum(1 for o in out if o["state"] == "OK")
        return {"nodes": out, "majority": self.majority, "healthy": healthy,
                "consensus_ok": healthy >= self.majority}

    def tamper(self, node_idx, block_index=None, field="payload_hash"):
        n = self.nodes[node_idx]
        if not n.chain:
            return False
        i = block_index if block_index is not None else len(n.chain) - 1
        n.chain[i][field] = sha256("tampered:" + str(n.chain[i][field]))
        return True

    def heal(self):
        good = [n for n in self.nodes if n.first_bad_index() is None]
        if len(good) < self.majority:
            return False
        ref = max(good, key=lambda n: sum(1 for m in good if m.head()["block_hash"] == n.head()["block_hash"]))
        for n in self.nodes:
            if n is not ref:
                n.chain = copy.deepcopy(ref.chain)
        return True
