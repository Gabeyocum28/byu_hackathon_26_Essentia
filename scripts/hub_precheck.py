"""Precheck for 'The Repair': measure hubness on the LIVE corpus via the tunnel.

Read-only against Redis. Answers:
  1. Does uncorrected surprise collapse onto one track? (N_1 share, farthest-query)
  2. Does the shipped centering correction disperse it?
  3. Does nearest-neighbor N_10 skewness grow with projection rank r?
  4. How long does the n x n similarity matrix take at this scale?
"""
import json
import time

import numpy as np
import redis

r = redis.Redis(host="localhost", port=16379, decode_responses=True)
ids = sorted(r.smembers("corpus:ids"))
print(f"corpus ids: {len(ids)}")

t0 = time.time()
vecs, kept = [], []
B = 200
for i in range(0, len(ids), B):
    chunk = ids[i:i + B]
    raw = r.mget([f"features:{t}" for t in chunk])
    for tid, blob in zip(chunk, raw):
        if not blob:
            continue
        f = json.loads(blob)
        emb = f.get("embedding")
        if emb and len(emb) == 1280:
            kept.append(tid)
            vecs.append(emb)
X = np.asarray(vecs, dtype=np.float64)
n, d = X.shape
print(f"embedding matrix: {X.shape}  fetch+parse {time.time()-t0:.1f}s")

U = X / np.linalg.norm(X, axis=1, keepdims=True)

t0 = time.time()
S = U @ U.T                      # (n, n) cosine similarity
t_mat = time.time() - t0
print(f"n x n matmul: {t_mat:.2f}s  ({S.nbytes/1e6:.0f} MB)")

c = U @ U.mean(axis=0)           # centrality, same identity as rank.centrality

# ---- 1. uncorrected surprise: winner = argmin cos(s, x), self excluded ----
S_no_self = S.copy()
np.fill_diagonal(S_no_self, np.inf)      # inf so argmin never picks self
win_unc = np.argmin(S_no_self, axis=1)
counts_unc = np.bincount(win_unc, minlength=n)
order = np.argsort(counts_unc)[::-1]
print("\n--- UNCORRECTED surprise N_1 (farthest-query) ---")
top10_share = 0
for j in order[:10]:
    share = counts_unc[j] / n
    top10_share += share
    meta = json.loads(r.get(f"track:{kept[j]}") or "{}")
    print(f"  {counts_unc[j]:4d} seeds ({share:5.1%})  c={c[j]:+.3f}  "
          f"{meta.get('artist','?')} - {meta.get('title','?')}")
print(f"  top-1 share {counts_unc[order[0]]/n:.1%}, top-5 share "
      f"{counts_unc[order[:5]].sum()/n:.1%}, top-10 {top10_share:.1%}")


def skew(x):
    x = np.asarray(x, dtype=float)
    m = x.mean()
    s2 = ((x - m) ** 2).mean()
    return float(((x - m) ** 3).mean() / (s2 ** 1.5 + 1e-12))


print(f"  N_1 skewness (uncorrected): {skew(counts_unc):.1f}")

# ---- 2. corrected surprise: winner = argmax(c[x] - cos(s, x)) ------------
adj = c[None, :] - S
np.fill_diagonal(adj, -np.inf)
win_cor = np.argmax(adj, axis=1)
counts_cor = np.bincount(win_cor, minlength=n)
order_c = np.argsort(counts_cor)[::-1]
print("\n--- CORRECTED surprise N_1 (shipped ranker) ---")
for j in order_c[:5]:
    meta = json.loads(r.get(f"track:{kept[j]}") or "{}")
    print(f"  {counts_cor[j]:4d} seeds ({counts_cor[j]/n:5.1%})  c={c[j]:+.3f}  "
          f"{meta.get('artist','?')} - {meta.get('title','?')}")
print(f"  top-1 share {counts_cor[order_c[0]]/n:.1%}, top-5 "
      f"{counts_cor[order_c[:5]].sum()/n:.1%}")
print(f"  N_1 skewness (corrected): {skew(counts_cor):.1f}")
print(f"  distinct winners: uncorrected {np.count_nonzero(counts_unc)}, "
      f"corrected {np.count_nonzero(counts_cor)}")

# ---- 3. classical nearest-neighbor hub: N_10 at full d -------------------
np.fill_diagonal(S_no_self, -np.inf)     # now for NEAREST queries
K = 10
nn = np.argpartition(-S_no_self, K, axis=1)[:, :K]
counts_nn = np.bincount(nn.ravel(), minlength=n)
order_nn = np.argsort(counts_nn)[::-1]
print(f"\n--- NEAREST-neighbor N_{K} hubs (full 1280-d) ---")
for j in order_nn[:5]:
    meta = json.loads(r.get(f"track:{kept[j]}") or "{}")
    print(f"  N_10={counts_nn[j]:4d} (expected {K})  c={c[j]:+.3f}  "
          f"{meta.get('artist','?')} - {meta.get('title','?')}")
print(f"  N_10 skewness at d=1280: {skew(counts_nn):.2f}  "
      f"(Poisson(10) null skew = {1/np.sqrt(K):.2f})")
print(f"  corr(N_10, centrality) = "
      f"{np.corrcoef(counts_nn, c)[0,1]:.2f}")

# ---- 4. skewness vs projection rank r ------------------------------------
t0 = time.time()
mu = U.mean(axis=0)
C = U - mu
_, _, Vt = np.linalg.svd(C, full_matrices=False)
print(f"\nfull SVD: {time.time()-t0:.1f}s")
print("--- N_10 skewness vs top-r PCA projection (renormalized) ---")
for rr in (2, 4, 8, 16, 32, 64, 128, 256, 512, 1280):
    P = C @ Vt[:rr].T
    Pn = P / (np.linalg.norm(P, axis=1, keepdims=True) + 1e-12)
    Sr = Pn @ Pn.T
    np.fill_diagonal(Sr, -np.inf)
    nnr = np.argpartition(-Sr, K, axis=1)[:, :K]
    cr = np.bincount(nnr.ravel(), minlength=n)
    print(f"  r={rr:5d}: skew={skew(cr):6.2f}  max N_10={cr.max():4d}")
