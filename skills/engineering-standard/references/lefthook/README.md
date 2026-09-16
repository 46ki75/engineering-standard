# Lefthook

Keep successful hook runs silent and show failures. Set the top-level [`output`](https://lefthook.dev/configuration/output/) option in `lefthook.yml`:

```yaml
output: false
```

Failed commands still print their output and return a nonzero exit status. Git's own output is controlled separately.

Verified with Lefthook 2.1.14. Configuration changes can produce a one-time `sync hooks` message; run the repository's hook-install command before verifying silence.
