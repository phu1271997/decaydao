import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  CONTRACT_ADDRESS,
  connectWallet,
  fetchLicenses,
  grantLicense,
  reviewLicense,
  reinstateLicense,
  humanizeError,
  hasMetaMask,
} from "./genlayer.js";

const VERDICT_META = {
  COMPLIANT: { label: "Honouring", tone: "good" },
  DRIFTING: { label: "Drifting", tone: "warn" },
  VIOLATED: { label: "Breached", tone: "bad" },
  "": { label: "Unreviewed", tone: "idle" },
};

function shortAddr(a) {
  if (!a) return "";
  return a.length > 12 ? `${a.slice(0, 6)}…${a.slice(-4)}` : a;
}

function HealthMeter({ value, max, status }) {
  const pct = Math.max(0, Math.min(100, Math.round((value / max) * 100)));
  const decayed = status === "REVOKED";
  return (
    <div className="meter" aria-label={`Health ${pct} percent`}>
      <div
        className={`meter-fill ${decayed ? "meter-dead" : ""}`}
        style={{ width: `${pct}%` }}
      />
      <span className="meter-num">{value}</span>
    </div>
  );
}

function LicenseCard({ lic, onReview, onReinstate, busyId, connected }) {
  const meta = VERDICT_META[lic.last_verdict] || VERDICT_META[""];
  const revoked = lic.status === "REVOKED";
  const busy = busyId === lic.id;
  return (
    <article className={`card ${revoked ? "card-revoked" : ""}`}>
      <header className="card-top">
        <div>
          <div className="eyebrow">License #{lic.id}</div>
          <h3 className="asset">{lic.asset}</h3>
        </div>
        <span className={`verdict verdict-${meta.tone}`}>{meta.label}</span>
      </header>

      <p className="terms">“{lic.terms}”</p>

      <HealthMeter value={lic.health} max={lic.max_health} status={lic.status} />

      <dl className="meta-grid">
        <div>
          <dt>Watching</dt>
          <dd>
            <a href={lic.monitored_url} target="_blank" rel="noreferrer">
              {lic.monitored_url}
            </a>
          </dd>
        </div>
        <div>
          <dt>Licensee</dt>
          <dd className="mono">{shortAddr(lic.licensee)}</dd>
        </div>
        <div>
          <dt>Reviews</dt>
          <dd>{lic.review_count}</dd>
        </div>
        <div>
          <dt>Confidence</dt>
          <dd>{lic.last_verdict ? `${lic.last_confidence}%` : "—"}</dd>
        </div>
      </dl>

      {lic.last_reason && lic.last_reason !== "Not yet reviewed." && (
        <p className="reason">
          <span className="reason-tag">Jury</span> {lic.last_reason}
        </p>
      )}

      <footer className="card-actions">
        {!revoked ? (
          <button
            className="btn"
            disabled={!connected || busy}
            onClick={() => onReview(lic.id)}
          >
            {busy ? "Convening jury…" : "Review against live page"}
          </button>
        ) : (
          <button
            className="btn btn-ghost"
            disabled={!connected || busy}
            onClick={() => onReinstate(lic.id)}
          >
            {busy ? "Reinstating…" : "Reinstate (licensor)"}
          </button>
        )}
      </footer>
    </article>
  );
}

export default function App() {
  const [address, setAddress] = useState("");
  const [licenses, setLicenses] = useState([]);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState("");
  const [granting, setGranting] = useState(false);
  const [error, setError] = useState("");
  const [toast, setToast] = useState("");

  const [form, setForm] = useState({
    licensee: "",
    asset: "",
    terms: "",
    url: "",
  });

  const configured = useMemo(() => !!CONTRACT_ADDRESS, []);

  const refresh = useCallback(async () => {
    if (!configured) {
      setLoading(false);
      return;
    }
    try {
      const list = await fetchLicenses();
      list.sort((a, b) => Number(b.id) - Number(a.id));
      setLicenses(list);
    } catch (e) {
      setError(humanizeError(e));
    } finally {
      setLoading(false);
    }
  }, [configured]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const flash = (m) => {
    setToast(m);
    setTimeout(() => setToast(""), 3500);
  };

  async function onConnect() {
    setError("");
    try {
      const a = await connectWallet();
      setAddress(a);
      flash("Wallet connected on GenLayer Studio.");
    } catch (e) {
      setError(humanizeError(e));
    }
  }

  async function onGrant() {
    setError("");
    if (!form.asset.trim() || !form.terms.trim() || !form.url.trim()) {
      setError("Asset, terms, and monitored URL are all required.");
      return;
    }
    setGranting(true);
    try {
      await grantLicense(address, {
        licensee: form.licensee.trim() || address,
        asset: form.asset.trim(),
        terms: form.terms.trim(),
        url: form.url.trim(),
      });
      setForm({ licensee: "", asset: "", terms: "", url: "" });
      flash("License granted. It starts at full health.");
      await refresh();
    } catch (e) {
      setError(humanizeError(e));
    } finally {
      setGranting(false);
    }
  }

  async function onReview(id) {
    setError("");
    setBusyId(id);
    try {
      await reviewLicense(address, id);
      flash("Jury ruled. Health updated.");
      await refresh();
    } catch (e) {
      setError(humanizeError(e));
    } finally {
      setBusyId("");
    }
  }

  async function onReinstate(id) {
    setError("");
    setBusyId(id);
    try {
      await reinstateLicense(address, id);
      flash("License reinstated under probation.");
      await refresh();
    } catch (e) {
      setError(humanizeError(e));
    } finally {
      setBusyId("");
    }
  }

  const connected = !!address;

  return (
    <div className="wrap">
      <div className="bg-grain" aria-hidden />

      <header className="masthead">
        <div className="brand">
          <span className="mark" aria-hidden>◷</span>
          <span className="brand-name">DecayDAO</span>
        </div>
        <div className="wallet">
          {connected ? (
            <span className="pill mono">{shortAddr(address)}</span>
          ) : (
            <button className="btn btn-connect" onClick={onConnect} disabled={!hasMetaMask()}>
              {hasMetaMask() ? "Connect wallet" : "Install MetaMask"}
            </button>
          )}
        </div>
      </header>

      <section className="hero">
        <h1 className="headline">
          Licenses that <em>read the world</em><br />and quietly decay when broken.
        </h1>
        <p className="dek">
          Grant a right to use your asset under terms written in plain language.
          A decentralized jury of AIs reads the licensee's live page, judges the
          <strong> spirit</strong> of the deal, and lets the license lose health
          every time it drifts — until it revokes itself. No adjudicator. No
          oracle.
        </p>
      </section>

      {!configured && (
        <div className="banner banner-warn">
          No contract address configured. Set <code>VITE_CONTRACT_ADDRESS</code> in
          your environment and redeploy, then reload.
        </div>
      )}

      <main className="grid">
        <section className="panel grant-panel">
          <h2 className="panel-title">Grant a license</h2>
          <label className="field">
            <span>Asset</span>
            <input
              placeholder="ACME wordmark"
              value={form.asset}
              onChange={(e) => setForm({ ...form, asset: e.target.value })}
            />
          </label>
          <label className="field">
            <span>Terms — the spirit, in your words</span>
            <textarea
              rows={3}
              placeholder="Non-commercial use only. Must credit ACME. No use next to gambling or hate content."
              value={form.terms}
              onChange={(e) => setForm({ ...form, terms: e.target.value })}
            />
          </label>
          <label className="field">
            <span>Live page to watch</span>
            <input
              placeholder="https://licensee-site.example/usage"
              value={form.url}
              onChange={(e) => setForm({ ...form, url: e.target.value })}
            />
          </label>
          <label className="field">
            <span>Licensee address (optional)</span>
            <input
              className="mono"
              placeholder="defaults to you"
              value={form.licensee}
              onChange={(e) => setForm({ ...form, licensee: e.target.value })}
            />
          </label>
          <button
            className="btn btn-primary"
            onClick={onGrant}
            disabled={!connected || granting}
          >
            {granting ? "Granting…" : "Grant license"}
          </button>
          {!connected && (
            <p className="hint">Connect a funded GenLayer Studio wallet to grant.</p>
          )}
        </section>

        <section className="panel list-panel">
          <div className="list-head">
            <h2 className="panel-title">Live licenses</h2>
            <button className="btn btn-ghost small" onClick={refresh}>
              Refresh
            </button>
          </div>

          {loading ? (
            <div className="empty">Reading the chain…</div>
          ) : licenses.length === 0 ? (
            <div className="empty">
              No licenses yet. Grant the first one on the left.
            </div>
          ) : (
            <div className="cards">
              {licenses.map((lic) => (
                <LicenseCard
                  key={lic.id}
                  lic={lic}
                  onReview={onReview}
                  onReinstate={onReinstate}
                  busyId={busyId}
                  connected={connected}
                />
              ))}
            </div>
          )}
        </section>
      </main>

      <footer className="foot">
        <span>
          Contract{" "}
          <span className="mono">{CONTRACT_ADDRESS ? shortAddr(CONTRACT_ADDRESS) : "—"}</span>{" "}
          on GenLayer Studio
        </span>
        <span className="foot-tag">A synthetic jurisdiction for IP.</span>
      </footer>

      {error && (
        <div className="banner banner-error" role="alert" onClick={() => setError("")}>
          {error} <span className="dismiss">✕</span>
        </div>
      )}
      {toast && <div className="toast">{toast}</div>}
    </div>
  );
}
