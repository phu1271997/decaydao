// genlayer.js — thin wrapper around genlayer-js that:
//  - connects an ALREADY-FUNDED MetaMask wallet and lets IT sign (R21, R22)
//  - switches/adds the GenLayer Studio network on connect (R23)
//  - keeps contract + chain + wallet all on the SAME network (R24)
//
// No private key is ever read in the frontend. MetaMask signs.

import { createClient } from "genlayer-js";
import { studionet } from "genlayer-js/chains";

// The hosted GenLayer Studio RPC. genlayer-js's `simulator` chain has the right
// chain id (61999) but defaults to localhost, so we override the endpoint to
// point at hosted Studio. Override via VITE_GENLAYER_RPC if you use localnet.
const STUDIO_RPC =
  import.meta.env.VITE_GENLAYER_RPC || "https://studio.genlayer.com/api";

// Studionet network params (verified in common_error.md R23).
export const STUDIONET_CHAIN_ID = 61999; // 0xF1EF
const CHAIN_ID_HEX = "0x" + STUDIONET_CHAIN_ID.toString(16);

export const CONTRACT_ADDRESS = import.meta.env.VITE_CONTRACT_ADDRESS || "";

// Chain object bound to the hosted Studio endpoint.
const chain = {
  ...studionet,
  rpcUrls: { default: { http: [STUDIO_RPC] } },
};

export function hasMetaMask() {
  return typeof window !== "undefined" && !!window.ethereum;
}

// Ensure MetaMask is on the GenLayer Studio network; add it if missing.
export async function ensureNetwork() {
  if (!hasMetaMask()) throw new Error("MetaMask not found. Please install it to continue.");
  try {
    await window.ethereum.request({
      method: "wallet_switchEthereumChain",
      params: [{ chainId: CHAIN_ID_HEX }],
    });
  } catch (err) {
    if (err.code === 4902 || err.code === -32603) {
      await window.ethereum.request({
        method: "wallet_addEthereumChain",
        params: [
          {
            chainId: CHAIN_ID_HEX,
            chainName: "GenLayer Studio Network",
            nativeCurrency: { name: "GEN Token", symbol: "GEN", decimals: 18 },
            rpcUrls: ["https://studio.genlayer.com/api"],
            blockExplorerUrls: ["https://genlayer-explorer.vercel.app"],
          },
        ],
      });
    } else {
      throw err;
    }
  }
}

// Connect wallet -> returns the active address. Caller passes this address into
// createClient so MetaMask signs each transaction.
export async function connectWallet() {
  if (!hasMetaMask()) throw new Error("MetaMask not found. Please install it to continue.");
  await ensureNetwork();
  const accounts = await window.ethereum.request({ method: "eth_requestAccounts" });
  if (!accounts || accounts.length === 0) throw new Error("No account selected in MetaMask.");
  return accounts[0];
}

// A read-only client (no account) is enough for views.
export function makeReadClient() {
  return createClient({ chain, endpoint: STUDIO_RPC, account: "0x0000000000000000000000000000000000000000" });
}

// A signing client bound to the connected address (MetaMask signs).
export function makeWriteClient(address) {
  return createClient({ chain, endpoint: STUDIO_RPC, account: address });
}

// ---- contract calls --------------------------------------------------------

export async function fetchLicenses() {
  const client = makeReadClient();
  const raw = await client.readContract({
    address: CONTRACT_ADDRESS,
    functionName: "get_all_licenses",
    args: [],
  });
  // get_all_licenses returns a JSON string.
  if (typeof raw === "string") {
    try {
      return JSON.parse(raw);
    } catch {
      return [];
    }
  }
  return Array.isArray(raw) ? raw : [];
}

export async function grantLicense(address, { licensee, asset, terms, url }) {
  const client = makeWriteClient(address);
  const hash = await client.writeContract({
    address: CONTRACT_ADDRESS,
    functionName: "grant_license",
    args: [licensee, asset, terms, url],
    value: 0n,
  });
  await client.waitForTransactionReceipt({
    hash,
    status: "FINALIZED",
    retries: 100,
    interval: 5000,
  });
  return hash;
}

export async function reviewLicense(address, licenseId) {
  const client = makeWriteClient(address);
  const hash = await client.writeContract({
    address: CONTRACT_ADDRESS,
    functionName: "review_license",
    args: [String(licenseId)],
    value: 0n,
  });
  // Non-deterministic tx (web + LLM + consensus) — this is the slow one.
  await client.waitForTransactionReceipt({
    hash,
    status: "FINALIZED",
    retries: 200,
    interval: 5000,
  });
  return hash;
}

export async function reinstateLicense(address, licenseId) {
  const client = makeWriteClient(address);
  const hash = await client.writeContract({
    address: CONTRACT_ADDRESS,
    functionName: "reinstate_license",
    args: [String(licenseId)],
    value: 0n,
  });
  await client.waitForTransactionReceipt({
    hash,
    status: "FINALIZED",
    retries: 100,
    interval: 5000,
  });
  return hash;
}

// Friendly-error mapping for the UI.
export function humanizeError(err) {
  const msg = (err && (err.message || String(err))) || "Unknown error";
  if (msg.includes("'from'")) {
    return "Wrong network in MetaMask. Reconnect so the app can switch you to GenLayer Studio.";
  }
  if (msg.toLowerCase().includes("insufficient funds")) {
    return "This wallet has no GEN on GenLayer Studio. Fund it from the Studio Accounts panel, then try again.";
  }
  if (msg.toLowerCase().includes("user rejected")) {
    return "You rejected the transaction in MetaMask.";
  }
  if (msg.includes("License not found")) {
    return "That license no longer exists.";
  }
  if (msg.includes("already revoked")) {
    return "This license is already revoked.";
  }
  return msg;
}
