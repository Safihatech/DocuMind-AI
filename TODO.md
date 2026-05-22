# TODO
- [x] Confirm how app is run (docker-compose vs python/uvicorn) and reproduce the `chroma` DNS error
- [x] Patch `app/core/vector_store.py` to fail fast + fallback when remote Chroma is unreachable
- [ ] (Optional) Improve frontend landing/UX while keeping upload flow working
- [ ] Run minimal smoke test: start stack, upload doc, run `/qa/query`
- [ ] Verify that citations + indexing status polling work

