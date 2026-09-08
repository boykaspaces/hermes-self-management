# File Map

Status: Current index

| Path | Owns | Read when |
|---|---|---|
| `README.md` | Repository entry, validation, and related components | Entering the repository |
| `PROJECT.md` | Stable identity and source-of-truth boundaries | Maintaining the project |
| `AGENTS.md` | Repository-wide AI instructions | Before changing files |
| `.context-kit/index.md` | Current-first public maintenance router | Resuming repository work |
| `tasks/` | Component Task state and current pointer | Reviewing or continuing development |
| `docs/decisions/README.md` | Public component decision index | Work depends on a durable repository decision |
| `deploy/README.md` | Deployment domain router | Choosing a Stack or operation |
| `deploy/QUICKSTART.md` | Public fresh-clone to Change Set runbook | Reproducing Hermes in a new AWS account |
| `deploy/bootstrap/` | Optional discovery, network, and artifact-bucket bootstrap | Preparing first-deployment prerequisites |
| `deploy/minimal/cloudformation.yaml` | Hermes host and bootstrap implementation | Changing runtime infrastructure |
| `deploy/minimal/README.md` | Current host deployment and validation flow | Deploying or upgrading Hermes |
| `deploy/minimal/HERMES_UPGRADE_RUNBOOK.md` | Version/patch migration and rollback gate | Changing Hermes revision |
| `deploy/minimal/MODEL_PROVIDER_STRATEGY.md` | Subscription-first provider policy | Changing model authentication or fallback |
| `deploy/minimal/patches/` | Version-specific upstream patch evidence | Porting or auditing a patch set |
| `deploy/minimal/policies/` | Parameterized host deployer/operator examples | Granting AWS access |
| `deploy/hermes-runtime-secrets/` | Retained Telegram Secret Stack and policy examples | Managing runtime credentials |
| `deploy/budget/` | Model cutoff/account budget Stack and policy examples | Managing cost controls |
| `hermes-plugins/observability/token_observer/` | Redacted usage collection, reports, viewer, service, and tests | Changing observability |
| `scripts/validate.sh` | Repository-wide static and unit validation | Before release or publication |
