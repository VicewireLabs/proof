# Vicewire proof

Vicewire is a private single-player GTA VI prototype with a Solana devnet wallet companion. On November 27, 2026, a simulated delivery paid **0.002 test SOL** to a newly generated player wallet. The treasury used faucet funds. Story Mode missions still award ordinary game cash. A live mission trigger, proof that a player controls their paired wallet, and deposits from $VICEWIRE creator fees are future integrations.

## Check the payout

[Open the finalized transaction in Solana Explorer](https://explorer.solana.com/tx/44XwNDhiLtd5k3iNzgRJmwYjYqukPJwNH4a4QHpML38rvFYJMgp2En7JnSh7ta3aNNCXCLqobCvCqcqGxMmra6hL?cluster=devnet). At slot **526954858**, the player gained **2,000,000 lamports** and the treasury spent **2,005,000 lamports**, including the **5,000-lamport network fee**.

Run either command from this directory with Python 3.11 or later. The live verifier reads Solana's public devnet RPC. It checks the network, signature, slot, transfer program, sender, recipient, amount, fee and both balance changes. It needs no wallet, credentials or third-party packages.

```sh
python verify.py --live
python verify.py
```

The second command checks the [bundled transaction](evidence/finalized-transaction.json). The [rehearsal record](evidence/devnet-rehearsal.json) describes the application-side test. Four concurrent reports supplied different candidate blockhashes and obtained one signed transfer. The harness discarded the submission acknowledgement. A fresh process recovered the finalized receipt from the journal. A repeat report returned the same receipt. The chain independently establishes the transfer and balance changes. The concurrency and restart results come from the harness.

## Windows PC capture

![Frame captured from the running game on Windows](media/pc-scene.jpg)

[Watch the outdoor scene](media/pc-scene.mp4) or [view a separate save-menu capture](media/pc-save-menu.jpg). These came from the game renderer of an emulated console build on Windows. We sampled 60 game-only frames over 11.7 seconds at a target of five captures per second. The clip is silent.

The renderer logged **22 samples** from startup through the outdoor scene. The samples ranged from **2.6 to 30.2 FPS**, with a median of **21.0 FPS**. Seven reached at least 30 FPS. The two samples ending during this clip measured **19.6** and **18.8 FPS**. Each row in the [renderer CSV](evidence/pc-renderer-samples.csv) includes its UTC time and whether it fell inside the capture window. [Capture timing and summary](evidence/pc-run.json)

## Wallet, checkout and branding

| What we tested | Observed result | Evidence |
|---|---|---|
| Read-only wallet pairing | A Wallet Standard browser fixture recovered after connection rejection, preserved pairing after reload and required a new selection after account changes. It requested no wallet signature. | [Pairing results](evidence/wallet-pairing.json) · [Companion preview](media/wallet-companion.jpg) |
| Public devnet balance | The companion and CLI agreed on a finalized public account balance within the recorded slot window. This was a watch-address check. | [Balance comparison](evidence/devnet-balance-read.json) |
| Local merchant checkout | A test signer paid 0.1 SOL to the merchant plus a 0.002 SOL service fee. Four verifiers credited a single companion entitlement, which survived a restart. | [Local checkout](evidence/local-checkout.json) |
| Devnet checkout simulation | An unsigned checkout simulation succeeded. This exercise issued no customer payment. | [Simulation](evidence/devnet-checkout-simulation.json) |
| Purchase panel | The SDK simulator rendered quote and status fixtures. A signed player purchase and a native game entitlement remain unverified. | [Simulator states](evidence/purchase-panel.json) |
| Vicewire name and palm artwork | The clone's install check recorded 31 texture targets and 1,278 changed labels across 139 independently decoded tables, including 127 English labels. The art board shows decoded assets. The unlocked in-game bank screen still needs a capture. | [Install record](evidence/brand-install.json) · [Native-size crops](media/native-asset-crops.png) |

## Reproduce the replay test locally

The public harness creates two temporary identities and uses only faucet funds on a loopback validator. It requests four distinct blockhashes, prepares the same mission concurrently, submits one transfer, reopens its journal in another process and checks finalized transaction history and balances. Local signatures vary on each run.

With Python 3.13 and a local Solana test validator installed, start a fresh validator in its own directory. In another terminal:

```sh
python -m venv .venv
# Activate .venv using your shell's normal activation command.
python -m pip install -r requirements.txt
python -m unittest discover
python rehearse_local.py
```

The default validator port is 8899. If your validator uses another loopback port, pass it with `--port`. The [original local run](evidence/local-rehearsal.json) and a [fresh run of this published harness](evidence/local-reproduction.json) each produced one finalized player credit. The separate private bridge suite passed 41 tests at the milestone. Only the self-contained proof tests are included here.

## Intro film

[Watch the 14-second Vicewire intro](media/vicewire-intro.mp4). This is a promotional animation with original illustrations, titles and music. The PC capture and transaction receipt above are the evidence for gameplay and the test payout.

[File checksums](SHA256SUMS) cover the published evidence, media and verifier files.
