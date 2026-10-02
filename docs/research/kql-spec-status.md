# Research: Status of KDL Query Language (KQL) Specification

**Date:** October 2026  
**Subject:** Has the KDL Query Language specification (`QUERY-SPEC.md`) been officially and finally approved as part of KDL 2.0?  
**Verdict:** **No.** The query language specification has **not** been finalized or approved. It remains an unreleased, work-in-progress draft completely separate from the core KDL 2.0.0 language specification.

---

## 1. Primary Source Evidence

### 1.1. Explicit Statement in the Official KDL 2.0.0 Release Announcement
In the official GitHub Discussions announcement of the KDL 2.0.0 release by Kat Marchán (`zkat`, creator and lead author of KDL):

- **Source:** [GitHub Discussion #447 (Dec 22, 2024) — Official KDL 2.0.0 Spec Released!](https://github.com/kdl-org/kdl/discussions/447)
- **Direct quote:**
  > **KQL**
  >
  > `[!INFO]` *Note: these are provided for convenience, but as of the 2.0.0 KDL spec release, KQL itself is not finalized and should be considered a separate specification, alongside the Schema spec and others.*

### 1.2. Status Header in `QUERY-SPEC.md`
The file `QUERY-SPEC.md` itself explicitly documents its unreleased state:

- **Source:** [kdl-org/kdl — QUERY-SPEC.md (line 7)](https://github.com/kdl-org/kdl/blob/main/QUERY-SPEC.md)
- **Direct quote:**
  > *This document describes KQL `next`. It is unreleased.*

*(Note: In September 2021, an early draft was briefly labeled `1.0.0`, but in August 2022 via commit `69ac280`, it was demoted to `KQL next. It is unreleased.` when major breaking changes were introduced, and it has remained unreleased ever since).*

### 1.3. Scope of KDL 2.0 Finalization
The repository `README.md` notes:
> *KDL 2.0.0 has been finalized, and no further changes are expected.*

However, this refers strictly to the core KDL document language specification ([`SPEC.md`](https://github.com/kdl-org/kdl/blob/main/SPEC.md) and Internet-Draft [`draft-marchan-kdl2.md`](https://github.com/kdl-org/kdl/blob/main/draft-marchan-kdl2.md)), established in Release PR [#434](https://github.com/kdl-org/kdl/pull/434). That PR did **not** touch or finalize `QUERY-SPEC.md`.

---

## 2. Active Development and Open Incompatibilities (2025–2026)

Far from being finalized, KQL has been undergoing intense debates and grammar fixes due to conflicts introduced by KDL 2.0 itself:

### 2.1. Identifier Conflicts with KDL 2.0
In KDL 2.0, bare identifiers were expanded to allow characters like `>`, `<`, `,`, and `+`. This broke previous assumptions in the KQL grammar:
- **Issue [#489](https://github.com/kdl-org/kdl/issues/489) ("Incompatibilities KDL 2 <-> Query", Jan 2025):**
  Found that queries like `lorem+ipsum` or `[foo>1]` became ambiguous (e.g. is `foo>1` a property name or a comparison operator?).
- **PR [#500](https://github.com/kdl-org/kdl/pull/500) (merged Feb 2025):**
  Emergency patch that made whitespace mandatory around all query operators (`q-ws+`) to resolve ambiguity with KDL 2.0 bare identifiers.

### 2.2. Unmerged Discrepancies and Open Pull Requests
Multiple active PRs remain open in the official repository to resolve discrepancies between the written text and the formal grammar:
- **PR [#507](https://github.com/kdl-org/kdl/pull/507) (Open):** *Align KDL Query grammar with prose* (fixing undocumented `values()`/`props()` and clarifying `val()` vs `val(0)`).
- **PR [#520](https://github.com/kdl-org/kdl/pull/520) (Open):** *the argument to val() is optional*.
- **PR [#522](https://github.com/kdl-org/kdl/pull/522) (Open):** *KQL can only select nodes* (correcting text claiming KQL can extract specific data, when it currently only selects nodes).
- **PR [#526](https://github.com/kdl-org/kdl/pull/526) (Open):** *swap around order of comparisons to reduce local ambiguity*.
- **PR [#531](https://github.com/kdl-org/kdl/pull/531) (Open):** *clean up wording and remove deadlink* (removing obsolete references to "accessors").

### 2.3. Unresolved Architectural Issues
- **Issue [#525](https://github.com/kdl-org/kdl/issues/525):** Syntax ambiguity in `[a>b>c]`.
- **Issue [#521](https://github.com/kdl-org/kdl/issues/521):** Clarification of `top() + []` and `top() ++ []`.
- **Issue [#518](https://github.com/kdl-org/kdl/issues/518):** Unescaped newlines currently forbidden due to `q-ws := $node-space`.
- **Issue [#532](https://github.com/kdl-org/kdl/issues/532):** Extremely restrictive comment placement rules.
- **Issue [#373](https://github.com/kdl-org/kdl/issues/373):** Lack of pseudo-classes/matchers (such as `:not()`, `:is()`, or negative matching).

---

## 3. Reference Implementations

Neither of the official reference implementations maintained under `kdl-org` implements KQL:
- **`kdl-org/kdl-rs`** (Rust, v6.x for KDL 2.0): Implements parser, serializer, CST, and AST. Does **not** include KQL or query engine.
- **`kdl-org/kdljs`** (JavaScript, v0.3.x): Implements parser and serializer only.

---

## 4. Summary & Implications for `kdlquery`

1. **Current Status:** KQL is an unreleased draft (`next`). It is **not** an official part of the finalized KDL 2.0.0 specification.
2. **Current Project Decision:** The divergence documented in `kdlquery`'s `README.md` (relying on a clean, CSS3-style selector syntax) remains completely justified and valid. Adopting KQL now would mean building against an unstable moving target with known grammatical edge cases.
