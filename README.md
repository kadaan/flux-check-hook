[pre-commit](http://pre-commit.com) hook for working with [flux](http://fluxcd.io)


## Usage

```
-   repo: https://github.com/tarioch/flux-check-hook
    rev: v0.5.0
    hooks:
    -   id: check-flux-helm-values
```

The hook depends on the helm binary being available in the path (but it doesn't require to be able to connect to a cluster).
