# create-hayate 設計ドキュメント

> hayate プロジェクトの scaffold CLI。`uvx create-hayate my-app` の
> 「3 分で動く + テストが通る」体験を提供する内部設計メモ(日本語)。
> 各節は「決定 / 理由 / 却下した代替案」の形を基本とする。

## TL;DR

- `uvx create-hayate my-app --template api|workers|mcp` → テスト付きの動くプロジェクト一式を生成。
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
- **却下**: ウィザード型の多段質問(DB は? auth は? lint は? …)— 決定疲れを起こし、
  テンプレートの直交積がメンテ不能になる。組み合わせはテンプレート単位で固定する。

## 3. テンプレート(v0.1)

| 名前 | 内容 | 検証 |
|---|---|---|
| `api` | TODO API + pytest(`app.request` 直叩き)+ uvicorn 起動 | `uv run pytest` |
| `workers` | 同一アプリ + wrangler.toml + pywrangler 構成。既定は `WorkerEntrypoint`、明示指定時のみ HTTP 専用 global handler | `uv run pytest`(+ README に `pywrangler dev` 手順) |
| `mcp` | 2025-11-25 tools server + Schema検証 + request context。ASGI / Workers共通 | `uv run pytest` + 実workerd |

- **方針: テンプレートの中身は本体 examples/ を正とする**。乖離は CI で検出(§5)。
- 変数置換は `string.Template`(`$project_name` 等)の最小限。ロジックをテンプレートに持ち込まない。
- `mcp`はhayate-authへ強制結合しない。既存IdP / managed accessをrequest contextから利用できる。
  将来: `lambda`(本体 aws アダプタ)、`auth + mcp`(組み込みAS需要の実測後)。

## 4. 実装(決定)

- 配布名 `create-hayate` / import 名 `create_hayate` / console_scripts エントリポイント。
  npm の `create-*` 慣習を Python に持ち込み、`uvx create-hayate` を唯一の推奨 UX とする
  (pipx / pip でも動く通常のパッケージ)。
- テンプレートは `importlib.resources` で同梱ファイルツリーをコピー。
- **却下**: cookiecutter / copier 依存 — ゼロ依存が崩れ、uvx 起動が重くなる。
  この規模に Jinja は要らない。
- **却下**: テンプレートのリモート取得(GitHub から fetch)— サプライチェーンリスクと
  オフライン不可。バージョン固定の同梱が正。

## 5. テスト戦略

- CI: 全テンプレート × 「生成 → `uv sync` → `uv run pytest`」を実行。
  Workers テンプレートはさらに実 workerd を起動し、HTTP 経由の CRUD まで固定する。
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
| 以降 | `lambda` / `auth + mcp`(需要実測後) | 同上 |

### 決定済み(2026-07-22)

| 項目 | 決定 |
|---|---|
| 名前 | **create-hayate**(配布名)/ `create_hayate`(import 名) |
| リポジトリ | `hayatepy/create-hayate`。private 開始、v0.1 完成時に公開判断 |
| ライセンス / 最低 Python | MIT / 3.12(本体に合わせる) |
| 依存 | ゼロ(stdlib のみ) |
