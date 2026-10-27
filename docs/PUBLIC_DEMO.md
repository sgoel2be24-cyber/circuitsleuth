# Temporary public demonstration

The team requested a working public URL with **zero cash spending**. The dated
endpoint is recorded in `submission/FORM_ANSWERS.json`. It runs the actual
OpenCV tool loop on the team Mac through a Cloudflare Quick Tunnel. It is
separate from the versioned AWS execution receipt.

This is a temporary development demonstration. Keep the Mac, server and tunnel
online; closing the lid, losing the network or stopping either process breaks
access. The hostname changes after creating a new tunnel. There is no uptime
guarantee. See [Cloudflare's documented limitations](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/).

## Run safely

After installing the locked dependencies, generating the demo fixtures and
building the frontend as described in README:

```bash
.venv/bin/python tools/public_demo.py --data-dir /tmp/circuitsleuth-public-demo --port 8102
cloudflared tunnel --no-autoupdate --protocol http2 --url http://127.0.0.1:8102
```

Use Cloudflare's official client. The final session used release `2026.10.4`;
the downloaded Darwin arm64 archive SHA256 was
`68b6bc4080ac1330234db2a9002d07f98b000537a1bd531a687b660d4160fa7f`,
matching its GitHub release digest. No account/domain/paid plan was created.

The launcher refuses directories inside the checkout and refuses an existing
non-demo directory. It uses only copied synthetic fixtures and its own run
store. Personal image uploads and capture attachment are disabled. The normal
local/AWS entrypoint retains its upload and capture pipeline.

Limits: 100 shared runs per session, 2 concurrent runs, 60 mutations/minute,
8 KB request bodies, at most 12 tool calls / 24 iterations. Stop and review
remain available when two runs are active. Both declared-length and streamed
bodies are bounded. Tests cover file/capture bypasses, over-budget inputs,
capacity and proxy-forwarded empty requests.

The public route disables SSE because Quick Tunnels do not support it. The
interface loads persisted events on entry/status changes and polls during
execution. A directly reloaded completed run recovered all 23 events.

To finish the session, stop the tunnel and server. The disposable directory
contains only public synthetic runs; preserve any desired demo evidence first.
The private original inspection store and the earlier private AWS resources
are separate and require their own cleanup.
