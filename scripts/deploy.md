# Deploy notes

Quick reference. Full detail is in the root README.

## 1. Contract (GenLayer Studio)

- https://studio.genlayer.com/run-debug
- Settings → Reset Storage → Confirm → hard refresh
- Deploy `contracts/storage_test.py` → confirm Result: SUCCESS
- Deploy `contracts/decaydao.py` (no constructor args) → confirm Result: SUCCESS
- Copy the contract address

Sanity calls:
    grant_license("0xLICENSEE", "ACME wordmark",
                  "Non-commercial use only. Must credit ACME.",
                  "https://example.org")
    review_license("0")
    get_license("0")
    get_all_licenses()

## 2. Frontend env

Set VITE_CONTRACT_ADDRESS to the copied address:
- local:  frontend/.env.local
- vercel: Project Settings → Environment Variables

## 3. Vercel

    cd frontend
    npm install
    npm run build      # sanity check
    npx vercel --prod  # or import the GitHub repo in the Vercel dashboard

Root directory in Vercel = `frontend`.

## 4. Fund the demo wallet

Transfer GEN to your MetaMask address from the Studio Accounts panel
(studionet). Do NOT use the testnet faucet for a studionet contract.

## Network facts

- chain id: 61999 (0xF1EF)
- rpc: https://studio.genlayer.com/api
- symbol: GEN, decimals: 18
