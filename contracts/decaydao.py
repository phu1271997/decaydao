# v0.2.16
# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
from genlayer import *

#
# DecayDAO - Self-adjusting IP licenses that read the real world.
# ---------------------------------------------------------------------------
# A licensor grants a licensee the right to use an asset (logo, brand, artwork,
# dataset, name) under TERMS WRITTEN IN NATURAL LANGUAGE ("the spirit of the
# license"). Traditional smart contracts cannot enforce a clause like
# "non-commercial use only" or "must credit the author" - they can neither read
# the licensee's live website nor judge whether a use honours the *spirit* of
# the grant.
#
# DecayDAO can. On every `review_license`, the contract fetches the licensee's
# live URL with gl.nondet.web.render and asks a decentralized LLM jury to rule
# COMPLIANT / DRIFTING / VIOLATED against the natural-language terms. Consensus
# is reached on the MEANING of the verdict (not its JSON shape), so two
# validators that word their rationale differently still agree. A license that
# drifts loses "health"; enough violations and it decays to REVOKED on-chain -
# no human adjudicator, no oracle.
#
# Why this DIES without GenLayer: the core is a subjective judgement over
# unstructured live web content, with a real grant of rights at stake, that no
# single party should decide alone. Remove the AI+web and nothing is left but a
# dumb key-value store.
# ---------------------------------------------------------------------------

import json
import typing
from dataclasses import dataclass


# --- Verdict vocabulary -----------------------------------------------------
# The health model: a license starts at MAX_HEALTH. Each review adjusts health.
#   COMPLIANT  -> +heal   (drift can recover if the licensee cleans up)
#   DRIFTING   -> -minor  (warning zone)
#   VIOLATED   -> -major  (serious breach)
# When health hits 0 the license is REVOKED and can no longer be used.

MAX_HEALTH = 100
HEAL_ON_COMPLIANT = 10
DECAY_ON_DRIFTING = 20
DECAY_ON_VIOLATED = 50

STATUS_ACTIVE = "ACTIVE"
STATUS_REVOKED = "REVOKED"


@allow_storage
@dataclass
class License:
    # Persisted integer fields MUST be bigint (see R14), never u256/int.
    licensor: str            # address (hex string) that granted the license
    licensee: str            # address (hex string) that holds the license
    asset: str               # what is licensed, e.g. "ACME wordmark"
    terms: str               # the SPIRIT, in natural language
    monitored_url: str       # live page the licensee controls
    health: bigint           # 0..MAX_HEALTH
    status: str              # ACTIVE | REVOKED
    review_count: bigint     # how many times it has been reviewed
    last_verdict: str        # COMPLIANT | DRIFTING | VIOLATED | (empty)
    last_confidence: bigint  # 0..100 from the jury
    last_reason: str         # human-readable rationale from the jury


def _addr_str(addr: Address) -> str:
    """Convert an Address to a stable string for map keys / JSON (R20)."""
    try:
        return addr.as_hex
    except Exception:
        return str(addr)


def _normalize_verdict(raw: str) -> str:
    """Map any LLM phrasing to one of the three canonical labels.

    Consensus is reached on THIS value, so it must be deterministic given the
    same semantic verdict. We never trust raw casing/whitespace/synonyms."""
    if raw is None:
        return "DRIFTING"
    v = str(raw).strip().upper()
    if "VIOLAT" in v or "BREACH" in v:
        return "VIOLATED"
    if "COMPL" in v or "OK" == v or "PASS" in v:
        return "COMPLIANT"
    if "DRIFT" in v or "WARN" in v or "PARTIAL" in v:
        return "DRIFTING"
    # Unknown wording defaults to the cautious middle state.
    return "DRIFTING"


class Contract(gl.Contract):
    # Storage. TreeMap keys are ALWAYS str (R19). Integers are bigint (R14).
    licenses: TreeMap[str, License]
    next_id: bigint

    def __init__(self):
        # Do NOT touch TreeMap here (R2) - GenVM auto-inits it to empty.
        self.next_id = bigint(0)

    # -----------------------------------------------------------------------
    # WRITE: create a license
    # -----------------------------------------------------------------------
    @gl.public.write
    def grant_license(
        self,
        licensee: str,
        asset: str,
        terms: str,
        monitored_url: str,
    ) -> None:
        """Licensor grants a natural-language license over an asset."""
        if not asset or not asset.strip():
            raise gl.vm.UserError("Asset description must not be empty")
        if not terms or not terms.strip():
            raise gl.vm.UserError("License terms must not be empty")
        if not monitored_url or not monitored_url.strip():
            raise gl.vm.UserError("Monitored URL must not be empty")
        if not (monitored_url.startswith("http://") or monitored_url.startswith("https://")):
            raise gl.vm.UserError("Monitored URL must start with http:// or https://")

        licensor_addr = _addr_str(gl.message.sender_address)

        lic = License(
            licensor=licensor_addr,
            licensee=licensee.strip(),
            asset=asset.strip(),
            terms=terms.strip(),
            monitored_url=monitored_url.strip(),
            health=bigint(MAX_HEALTH),
            status=STATUS_ACTIVE,
            review_count=bigint(0),
            last_verdict="",
            last_confidence=bigint(0),
            last_reason="Not yet reviewed.",
        )

        lid = str(self.next_id)
        self.licenses[lid] = lic
        self.next_id = self.next_id + bigint(1)

    # -----------------------------------------------------------------------
    # WRITE: review a license against the live web (THE HEART)
    # -----------------------------------------------------------------------
    @gl.public.write
    def review_license(self, license_id: str) -> None:
        """Fetch the monitored URL and let the AI jury rule on the SPIRIT of
        the terms. Adjusts health and may revoke. Anyone can call this - the
        point is that no single party decides."""
        if license_id not in self.licenses:
            raise gl.vm.UserError("License not found")

        lic = self.licenses[license_id]
        if lic.status == STATUS_REVOKED:
            raise gl.vm.UserError("License already revoked; nothing to review")

        # Capture locals for the nondet block (cannot touch self inside it).
        url = lic.monitored_url
        terms = lic.terms
        asset = lic.asset

        def leader_fn():
            # Read the licensee's live page directly on-chain - no oracle.
            page = gl.nondet.web.render(url, mode="text")
            if page is None:
                page = ""
            # Keep the prompt bounded; pages can be huge.
            evidence = page[:6000]

            prompt = f"""You are an impartial IP-license adjudicator on a decentralized court.

A licensor granted a license over this asset:
  ASSET: {asset}

The license terms, written in plain language (judge the SPIRIT, not just the letter):
  TERMS: {terms}

Below is the current live content of the page the licensee controls. Decide
whether the licensee's actual use honours the spirit of the license.

  LIVE PAGE CONTENT:
  ---
  {evidence}
  ---

Rules for your ruling:
- COMPLIANT: the use clearly honours the spirit of the terms.
- DRIFTING: the use is ambiguous, borderline, or shows early signs of breaching
  the spirit (e.g. creeping toward commercial use when non-commercial was required).
- VIOLATED: the use clearly breaches the spirit of the terms.
- If the page is empty, unreachable, or gives no evidence either way, rule DRIFTING
  with low confidence.

Respond with ONLY this JSON object and nothing else:
{{"verdict": "COMPLIANT" | "DRIFTING" | "VIOLATED", "confidence": <integer 0-100>, "reason": "<one or two sentences>"}}"""

            result = gl.nondet.exec_prompt(prompt, response_format="json")
            # exec_prompt(json) returns a dict; normalize to a canonical,
            # consensus-friendly payload. We deliberately DROP free-form prose
            # from what validators compare, keeping only the decision + a
            # bucketed confidence, so equivalence is about MEANING.
            verdict = _normalize_verdict(result.get("verdict", "DRIFTING"))
            try:
                conf = int(result.get("confidence", 0))
            except Exception:
                conf = 0
            conf = max(0, min(100, conf))
            reason = str(result.get("reason", "")).strip()[:400]

            return json.dumps(
                {"verdict": verdict, "confidence": conf, "reason": reason},
                sort_keys=True,
            )

        def validator_fn(leader_res: typing.Any) -> bool:
            # Validate the MEANING, not the schema (Axis 2). A validator agrees
            # only if its own independent ruling reaches the SAME verdict as the
            # leader, and the confidence is in the same broad band. Two honest
            # validators wording their reason differently still agree.
            if not isinstance(leader_res, gl.vm.Return):
                return False
            try:
                leader_payload = json.loads(leader_res.calldata)
            except Exception:
                return False

            leader_verdict = _normalize_verdict(leader_payload.get("verdict"))

            my_raw = json.loads(leader_fn())  # leader_fn is deterministic-shaped
            my_verdict = _normalize_verdict(my_raw.get("verdict"))
            if my_verdict != leader_verdict:
                return False

            # Confidence must land in the same coarse band (low/med/high) so a
            # 74 vs 78 disagreement doesn't fail consensus, but 20 vs 90 does.
            def band(c: int) -> int:
                try:
                    c = int(c)
                except Exception:
                    c = 0
                if c < 35:
                    return 0
                if c < 80:
                    return 1
                return 2

            return band(leader_payload.get("confidence", 0)) == band(my_raw.get("confidence", 0))

        raw = gl.vm.run_nondet_unsafe(leader_fn, validator_fn)
        payload = json.loads(raw)

        verdict = _normalize_verdict(payload.get("verdict"))
        try:
            confidence = int(payload.get("confidence", 0))
        except Exception:
            confidence = 0
        confidence = max(0, min(100, confidence))
        reason = str(payload.get("reason", "")).strip()[:400]

        # --- deterministic health model -----------------------------------
        health = int(lic.health)
        if verdict == "COMPLIANT":
            health = min(MAX_HEALTH, health + HEAL_ON_COMPLIANT)
        elif verdict == "DRIFTING":
            health = max(0, health - DECAY_ON_DRIFTING)
        else:  # VIOLATED
            health = max(0, health - DECAY_ON_VIOLATED)

        lic.health = bigint(health)
        lic.review_count = lic.review_count + bigint(1)
        lic.last_verdict = verdict
        lic.last_confidence = bigint(confidence)
        lic.last_reason = reason if reason else "No rationale provided."

        if health == 0:
            lic.status = STATUS_REVOKED

        self.licenses[license_id] = lic

    # -----------------------------------------------------------------------
    # WRITE: licensor can manually restore a cleaned-up license
    # -----------------------------------------------------------------------
    @gl.public.write
    def reinstate_license(self, license_id: str) -> None:
        """Only the original licensor may reinstate a revoked license (e.g.
        after the licensee fixed the violation). Resets to half health so it
        stays under scrutiny."""
        if license_id not in self.licenses:
            raise gl.vm.UserError("License not found")
        lic = self.licenses[license_id]
        caller = _addr_str(gl.message.sender_address)
        if caller != lic.licensor:
            raise gl.vm.UserError("Only the licensor can reinstate this license")
        if lic.status != STATUS_REVOKED:
            raise gl.vm.UserError("License is not revoked")
        lic.status = STATUS_ACTIVE
        lic.health = bigint(MAX_HEALTH // 2)
        lic.last_reason = "Reinstated by licensor; under probation."
        self.licenses[license_id] = lic

    # -----------------------------------------------------------------------
    # VIEWS
    # -----------------------------------------------------------------------
    @gl.public.view
    def get_license(self, license_id: str) -> str:
        """Return one license as a JSON string."""
        if license_id not in self.licenses:
            raise gl.vm.UserError("License not found")
        return self._license_to_json(license_id, self.licenses[license_id])

    @gl.public.view
    def get_all_licenses(self) -> str:
        """Return every license as a JSON array string (frontend reads this)."""
        out = []
        n = int(self.next_id)
        for i in range(n):
            lid = str(i)
            if lid in self.licenses:
                out.append(json.loads(self._license_to_json(lid, self.licenses[lid])))
        return json.dumps(out)

    @gl.public.view
    def get_count(self) -> int:
        return int(self.next_id)

    # -----------------------------------------------------------------------
    # helpers
    # -----------------------------------------------------------------------
    def _license_to_json(self, lid: str, lic: License) -> str:
        return json.dumps({
            "id": lid,
            "licensor": lic.licensor,
            "licensee": lic.licensee,
            "asset": lic.asset,
            "terms": lic.terms,
            "monitored_url": lic.monitored_url,
            "health": int(lic.health),
            "max_health": MAX_HEALTH,
            "status": lic.status,
            "review_count": int(lic.review_count),
            "last_verdict": lic.last_verdict,
            "last_confidence": int(lic.last_confidence),
            "last_reason": lic.last_reason,
        })
