# DecayDAO — IP licenses that read the world and decay when broken

> A synthetic jurisdiction for intellectual property. Grant a right to use your
> asset under terms written in plain language; a decentralized jury of AIs reads
> the licensee's live page, judges the **spirit** of the deal, and lets the
> license lose health every time it drifts — until it revokes itself on-chain.
> No human adjudicator. No oracle.

---

## The problem

IP licenses are frozen the moment they're signed. A licensor writes "you may use
our logo for **non-commercial** purposes" or "you must **credit** the artist" or
"don't place our brand next to **hate content**" — and then has no way to know,
let alone enforce, whether the licensee still honours that spirit six months
later. Enforcement today means a human periodically checking a website and a
lawyer arguing about intent. It doesn't scale, it's subjective, and one party
holds all the power to decide.

A normal smart contract can't help here. It can't read the licensee's live
website, and it can't judge whether "a shop tab appeared" violates the *spirit*
of a non-commercial grant. That judgement is exactly what GenLayer exists for.

## Why this dies without GenLayer

The core of DecayDAO is a **subjective judgement over unstructured live web
content, with a real grant of rights at stake, that no single party should
decide alone.** Remove the AI + web layer and nothing is left but a key-value
store of text. Specifically it needs three things only GenLayer provides:

1. **On-chain web access** — the contract fetches the licensee's live page with
   `gl.nondet.web.render`, no oracle in the loop.
2. **Subjective reasoning at consensus** — a jury of validators running diverse
   LLMs rules COMPLIANT / DRIFTING / VIOLATED against natural-language terms.
3. **Consensus on meaning, not format** — validators agree on the *verdict*,
   even when they word their rationale differently.

## How it works

```
 Licensor                          DecayDAO (Intelligent Contract)         GenLayer validators
    │  grant_license(asset, TERMS, url) │                                          │
    ├──────────────────────────────────▶│  stores license @ health 100            │
    │                                    │                                          │
 Anyone │  review_license(id)            │                                          │
    ├──────────────────────────────────▶│  leader: web.render(url) ──────────────▶ │ read live page
    │                                    │  leader: exec_prompt(TERMS + page) ─────▶ │ each LLM rules
    │                                    │  validators re-run & vote on the VERDICT │ consensus
    │                                    │◀─────────────────────────────────────────┤
    │                                    │  COMPLIANT → heal   DRIFTING → −20        │
    │                                    │  VIOLATED  → −50    health 0 → REVOKED    │
    │◀───────────────────────────────────┤  verdict + confidence + reason on-chain  │
```

A license starts at **100 health**. Each review adjusts it: `COMPLIANT` heals
(+10), `DRIFTING` decays (−20), `VIOLATED` decays hard (−50). At 0 the license is
`REVOKED`. The original licensor — and only them — can `reinstate` a cleaned-up
license at half health, keeping it under probation.

### The consensus design (why it's not just "check the JSON")

The contract does **not** reach consensus on the LLM's raw output. In
`review_license`, the validator function independently re-runs the ruling and
agrees only if its own verdict **means the same thing** as the leader's
(normalized to COMPLIANT / DRIFTING / VIOLATED) *and* the confidence lands in the
same coarse band. Two honest validators that phrase their reasons differently
still agree; a leader that flips the verdict fails consensus. That is the line
between a real Intelligent Contract and a format-checker.

## Repository layout

```
decaydao/
├── contracts/
│   ├── decaydao.py        # the Intelligent Contract (the heart)
│   └── storage_test.py    # minimal sanity contract — deploy this FIRST
├── frontend/              # Vite + React + genlayer-js dApp (deploys to Vercel)
│   ├── src/
│   │   ├── App.jsx        # full user flow + UI
│   │   ├── genlayer.js    # wallet + network + contract calls
│   │   └── styles.css
│   ├── .env.example
│   └── vercel.json
├── tests/
│   ├── test_decaydao.py   # gltest suite (mocked LLM/web)
│   └── gltest.config.yaml
└── scripts/
    └── deploy.md          # step-by-step deploy notes
```

---

## Part 1 — Deploy the contract on GenLayer Studio

1. Open <https://studio.genlayer.com/run-debug>.
2. **Settings → Reset Storage → Confirm**, then hard refresh (Cmd/Ctrl+Shift+R).
3. (Recommended) Deploy `contracts/storage_test.py` first. Confirm the tx shows
   `Result: SUCCESS`. This proves the environment is healthy before the real
   contract.
4. Deploy `contracts/decaydao.py`. Constructor takes no arguments.
5. Click the deploy transaction in the sidebar and confirm `Result: SUCCESS`
   (not just `Status: FINALIZED`).
6. **Copy the contract address.** You'll need it for the frontend.

Try it in Run & Debug:
- `grant_license("0xLICENSEE", "ACME wordmark", "Non-commercial use only. Must credit ACME.", "https://example.org")`
- `review_license("0")` — this is the slow one; it fetches the web and runs the
  LLM jury. Watch it reach consensus, then read `get_license("0")`.

> The contract follows every rule in `common_error.md`: `# v0.2.16` first line,
> class named `Contract`, `bigint` storage fields, `str`-keyed `TreeMap`,
> `@allow_storage @dataclass` structs, and all `gl.nondet.*` calls wrapped in
> `gl.vm.run_nondet_unsafe`.

## Part 2 — Wire the contract address into the frontend

You have the contract address from Part 1. Set it as `VITE_CONTRACT_ADDRESS`:

- **Local:** copy `frontend/.env.example` to `frontend/.env.local` and paste the
  address.
- **Vercel:** Project Settings → Environment Variables →
  `VITE_CONTRACT_ADDRESS = 0x…`.

Nothing else needs configuring; the RPC defaults to hosted Studio.

## Part 3 — Run locally

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173
```

## Part 4 — Deploy to Vercel

```bash
cd frontend
# push this repo to GitHub, then import it in Vercel, OR:
npx vercel --prod
```

Vercel auto-detects Vite (`vercel.json` is included). Set
`VITE_CONTRACT_ADDRESS` in the Vercel dashboard, redeploy, done.

### Using the live app (important — read once)

The app uses the **connect-wallet + user-signs** pattern (no private key in the
bundle). For a transaction to succeed:

1. Connect a MetaMask wallet that **already holds GEN on GenLayer Studio**. Fund
   it from the Studio **Accounts** panel (transfer GEN from a pre-funded Studio
   account). The public testnet faucet funds testnet, **not** studionet.
2. On connect, the app switches/adds the GenLayer Studio network (chain id
   `61999`) automatically.
3. Keep the contract, the frontend network, the wallet balance, and the funding
   source all on the **same** network. A contract deployed on studionet only
   exists on studionet.

If a write fails: check the connected wallet is funded on this network. A
MetaMask `'from'` error means the wrong network is active — reconnect to let the
app switch you.

## Part 5 — Tests

```bash
pip install genlayer-test
cd tests
gltest --network studionet
```

The suite mocks the LLM verdict and web page (so non-deterministic txs finalize
deterministically) and covers: compliant review heals, repeated violations drive
health to 0 and revoke, drifting lowers health, input guards, and licensor-only
reinstatement.

---

## One-line pitch

**DecayDAO is a license that reads the licensee's live website and quietly
revokes itself when the use stops honouring the spirit of the deal — impossible
without an AI jury reading the web at the consensus layer, which is exactly and
only what GenLayer does.**
