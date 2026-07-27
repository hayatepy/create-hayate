# create-hayate 設計ドキュメント

> hayate プロジェクトの scaffold CLI。`uvx create-hayate my-app` の
> 「3 分で動く + テストが通る」体験を提供する内部設計メモ(日本語)。
> 各節は「決定 / 理由 / 却下した代替案」の形を基本とする。

## TL;DR

- `uvx create-hayate my-app --template api|workers|mcp` → テスト付きの動くプロジェクト一式を生成。
- `--with admin,openapi,mcp,sql` と `--auth` は共通baseへ小さなcomponentを合成する。
- `--frontend none|htmx|react|astro` はruntime/feature/authと独立した最後の合成軸。
- htmxでは`--renderer jinja|htpy|jx|tdom`を選べ、Jinjaを互換defaultとする。
- `--template workers --preset production` は実運用導線を固定したgolden composition。
- **ゼロ依存**(argparse + shutil + string.Template のみ)。テンプレートはパッケージ内に同梱。
- 生成物は本体 examples/ と同水準の「テスト付き最小アプリ」。**CI が全テンプレートを
  生成 → `uv run pytest` まで回す**(テンプレート腐敗を防ぐのはこの一点)。
- v0.1 は api / workers、v0.2 は外部IdPと組み合わせられるauth非必須のmcpテンプレート。

```
$ uvx create-hayate my-app --template workers
$ cd my-app && uv run pytest   # グリーン
$ uv run pywrangler dev        # ローカル workerd で起動
```

## 1. なぜ作るか

- create-hono / Rails scaffold の教訓: **最初の 3 分で「動く + テストが通る」体験が採用を決める**。
  現状の hayate は Getting Started がコピペの列で、Workers 構成(wrangler.toml、pywrangler)は
  手組みするには足が重い。
- uv / uvx の普及で、npm `create-*` 相当のゼロインストール UX が Python でも成立するようになった。
- エコシステム(auth / mcp)が増えるほど「正しい組み合わせの初期形」の価値が上がる。

## 2. UX(決定)

```
uvx create-hayate my-app                          # 対話はテンプレート選択のみ
uvx create-hayate my-app --template workers --no-input   # CI / スクリプト用
```

- 質問は最小(テンプレートのみ。プロジェクト名は引数)。`--no-input` で完全非対話。
- 生成後に次の 3 手だけを表示: `cd` / `uv run pytest` / 起動(または deploy)コマンド。
- **却下**: ウィザード型の多段質問(DB は? auth は? lint は? …)— 決定疲れを起こす。
  組合せは非対話でも再現可能な明示flagと、review済みpresetで表現する。

## 3. Runtimeとcomponent

| 名前 | 内容 | 検証 |
|---|---|---|
| base | TODO API、identity/storage protocol、pytest | 全生成物 |
| observability | safe request ID、最終statusのquery-free JSON access event | direct/ASGI/workerd |
| `api` runtime | ASGI起動 | 実ASGI HTTP |
| `workers` runtime | wrangler/Pywrangler。既定は `WorkerEntrypoint` | 実workerd |
| `openapi` | typed path/response contract、OpenAPI 3.1.1、Scalar、TypeScript export | runtime/schema/型生成 |
| `mcp` | 2025-11-25、request context、storage共有 | ASGI/workerd |
| `sql` | migration、query contract、typed facade、SQLite/D1 | compile/実D1 |
| `admin` | 明示resource、owner scope、bounded query、永続redacted audit | SQLite/Chromium/workerd+D1 |
| `cloudflare-access` | local明示identity、本番JWT/JWKS検証 | auth境界 |
| `production` | CORS、header、body limit、rate limit、checklist | golden app |
| `frontend` | `none` / htmx / React / Astro の独立ownership境界 | overlay衝突検査 |
| `renderer` | Jinja / htpy / Jx / tdom のhtmx view境界 | strict型検査 + Chromium/workerd |

- 生成順はbase → runtime → feature → auth → production → frontend → renderer。既存componentは
  所有する境界だけを置換できるが、frontend overlayによるbackend file上書きは常に失敗する。
- observabilityは選択式componentにせず、全生成物のmiddleware登録順で常に最外周へ置く。
  `X-Request-ID`は保守的な文字集合と長さで検証し、access eventはmethod/path/final status/
  duration/request IDだけを持つ。query/header/bodyを既定で記録せず、request IDを認証情報として
  扱わない。
- `none` は互換defaultであり、既存commandの生成物を変えない。
- frontendは同じbackend templateを複製せず、profile固有の非衝突fileだけを合成する。
  htmxは`src/feature_htmx.py`、`templates/`、`public/`、profile/testを所有し、JSONとHTMLから
  共通のtodo domain/storageを呼ぶ。Reactは`frontend/`内のVite SPAと生成OpenAPI型だけを所有し、
  Hayateの`/api`を唯一のbackend contractとする。Astroも`frontend/`を所有するが静的出力を
  defaultとし、public contentはbuild時、identity依存dataは小さなPreact islandのhydrate後だけ
  同一originの`/api`から取得する。React/AstroのOpenAPI document・生成TypeScript型・clientは
  共通componentから合成し、profileごとの手書きmodelを持たない。Astro SSRはadapterを明示的に
  追加する将来のBFF拡張であり、初期runtimeには含めない。
  htmx package公開前はASGIがrelease-gate commitをVCS固定し、Workersは同commitのsourceと、
  deploy前にcanonical HTMLから再生成する`DictLoader` moduleを同梱する。
  Jinjaはこの生成物をbyte-for-byteで維持する互換defaultとする。htpyはASGI/Workers、
  JxはASGI、tdomはPython 3.14 ASGIのexperimental contractとし、renderer固有viewだけを
  独立overlayで追加する。route・identity・CRUD・CSRF/CSP・SSEは共通componentに残す。
  各profileのproduction contractが入るまではproduction presetとの併用を拒否する。
- `mcp`は互換shortcutであり、独立したfull templateを持たない。
- `mcp`はhayate-authへ強制結合しない。`none`または既存Cloudflare Accessを明示する。
- `admin`は`sql`とCloudflare Accessを自動合成し、`workers` runtimeかつ
  `frontend=none`のreview済み境界だけを許可する。これはWorkers専用application coreを
  意味せず、同じ生成物をASGI+SQLiteでも検証する。匿名mode/default superuserは生成しない。
  Access subjectでrecordとauditを分離し、operator email allowlist、exact Origin、
  bounded search/sort/page、値を含まないaudit historyを初期契約にする。
- `hayate-admin`/`hayate-htmx`公開前はreview済みcommitのMIT sourceを無改変で同梱し、
  commitとlicenseを生成物へ残す。PyPI公開後の置換はSQLite/Chromium/workerd+D1 gateを
  再実行する通常の依存更新として扱う。

## 4. 実装(決定)

- 配布名 `create-hayate` / import 名 `create_hayate` / console_scripts エントリポイント。
  npm の `create-*` 慣習を Python に持ち込み、`uvx create-hayate` を唯一の推奨 UX とする
  (pipx / pip でも動く通常のパッケージ)。
- componentは `importlib.resources` で同梱ファイルツリーを決定的順序でoverlayする。
- baseの `todo_api.py` は依存の軽いContext-first実装を持ち、OpenAPI componentだけが
  typed path/response版へ置換する。入力文字列の長さ制約はtyped stdlib surfaceが
  表現可能になるまでraw JSON Schemaを共用し、runtimeと文書の精度を落とさない。
- **却下**: cookiecutter / copier 依存 — ゼロ依存が崩れ、uvx 起動が重くなる。
  この規模に Jinja は要らない。
- **却下**: テンプレートのリモート取得(GitHub から fetch)— サプライチェーンリスクと
  オフライン不可。バージョン固定の同梱が正。

## 5. テスト戦略

- CI: legacy 40組合せ、admin 8組合せ、production/admin-production各2 entrypointの
  合計52構成を全て
  「生成 → dependency resolution → import」する。
- base Workers / MCP / productionを実workerdで起動する。productionはD1 migration後、
  Access identity付きHTTP writeをMCPからreadし、同一data/identity境界を固定する。
- golden appを実ASGIでも起動し、同じ`src/app.py`をSQLiteで検証する。
- observabilityは全生成物のdirect testでresponse ID・query非露出・context復元を検証し、
  production direct testでmiddleware 401/404の最終statusを固定する。実ASGIと実workerdでは
  process logから相関JSON行を読み、query secretが同じ行へ出ないことを検証する。
- admin profileは生成後direct request、実Chromium、ASGI+SQLite、実workerd+D1で
  認証/allowlist/owner scope/Origin/CRUD/search/sort/history/audit/bundle inclusionを固定する。
- htmx profileは生成後のdirect request、実Chromium、実workerdを通し、page/fragment、
  CRUD/validation/history/SSE、CSP/CSRF、Cloudflare Static Assetsを固定する。
- React profileは生成後のOpenAPI drift、TypeScript、Vite build、実Chromium CRUD/deep-link、
  npm audit、実workerdのAPI-first routing/SPA fallback/security headerを固定する。
- Astro profileは生成後のOpenAPI drift、TypeScript、静的build、private data非埋め込み監査、
  実Chromium CRUD/deep-link/custom 404、npm audit、実workerdのAPI-first routingと
  Cloudflare Static Assetsを固定する。
- frontend compatibilityはpackaged JSONをCLI allow-listとCIの単一source of truthにする。
  重複するimplicit featureを除いた112構成は維持し、PRではrenderer 4件を加えたwheel由来の
  10 boundary case、週次/手動では12 shardのfull matrixとして検証する。各caseは
  composition/renderer/phase/command/toolchain/wheel digest/timingをJSON evidenceに残し、
  失敗名だけで構成とphaseを特定できるようにする。
- 本体の新リリース時にテンプレートの hayate バージョンを上げる(Renovate 等は使わず
  リリースチェックリストに載せる。依存が hayate だけなので手動で足りる)。

## 6. リスクと対応

| リスク | 対応 |
|---|---|
| テンプレート陳腐化 | CI(§5)+ 本体リリースチェックリストに更新項目 |
| 本体 API 変更で全テンプレート壊れる | それ自体がドッグフーディング(v1.0 前に検出できる方が良い) |
| PyPI 名スクワット | `create-hayate` 空き確認 2026-07-22。0.0.x 早期公開で確保 |

## 7. マイルストーン

| 版 | 内容 | 受け入れ基準 |
|---|---|---|
| ~~v0.1~~ | **完了(2026-07-22)**: `api` / `workers` テンプレート + `--no-input` | ✅ 生成物の pytest グリーン(ローカル + CI)。✅ 3 手で起動到達(api=uvicorn、workers=ローカル workerd で CRUD 実測)。✅ CI が全テンプレート生成 → pytest(初回 run 全 green)。wheel 同梱・uvx 実行も確認 |
| ~~v0.2~~ | **完了(2026-07-25)**: `mcp`テンプレート。ASGI / Workers共通、hayate-auth非必須 | ✅ wheel生成物pytest。✅ 実ASGI / workerdでinitialize / tools/list / tools/call |
| ~~v0.3~~ | **完了(2026-07-26)**: Hayate 0.11同期、明示global entrypoint、bundle縮小 | ✅ 全runtime実測 |
| v0.4 | component合成とproduction golden path | ✅ 40組合せ+2 preset解決。✅ ASGI/SQLite。✅ workerd/D1 + Access + MCP |
| 以降 | `lambda` / 外部design partner由来のcomponent | 同上 |

### 決定済み(2026-07-22)

| 項目 | 決定 |
|---|---|
| 名前 | **create-hayate**(配布名)/ `create_hayate`(import 名) |
| リポジトリ | `hayatepy/create-hayate`。private 開始、v0.1 完成時に公開判断 |
| ライセンス / 最低 Python | MIT / 3.12(本体に合わせる) |
| 依存 | ゼロ(stdlib のみ) |
