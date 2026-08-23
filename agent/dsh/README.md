# DSH local harness

このbundleは既存のdeterministic risk engineをDSHの単一agentへ接続します。
モデルに公開するtoolは次の2つだけです。

- `get_decision_context`: risk snapshotと選択可能な候補を取得
- `submit_decision`: 候補を1つ選び、deterministic gateで検証してpaper dry-runを記録
- `get_alpaca_readonly_snapshot`: 公式Alpaca MCPからpaper account/positionsと
  SPY market dataを読み取り（注文・取消・account変更toolは非公開）

モデルは銘柄、注文、数量、risk値を自由生成できません。`submit_decision`の成功結果も
`human_approval_required: true`であり、Alpacaへは送信されません。

## Setup

Node.js 22以上を使用します。DSHはdeveloper previewのため、`package-lock.json`に
`0.1.1-rc.2`系の依存関係を固定しています。

```bash
cd agent/dsh
npm ci
DSH_HOME="$PWD/../../.dsh" ./node_modules/.bin/dsh \
  plugin --profile portfolio-agent add "$PWD"
```

## Keyless verification

HF token、Alpaca key、Modal secretを使わずに、calm / elevated / stressedの3状態を
official replay adapterで通します。

```bash
cd agent/dsh
npm test
npm run test:alpaca-schema
npm run test:profile
cd ../..
python3 -m unittest discover -s tests -v
```

`test:profile`は一時ディレクトリ内にDSH_HOMEとdry-run ledgerを作成します。
実account、remote model、paper orderには接続しません。
`test:alpaca-schema`は非secret placeholderでofficial serverを構築して`tools/list`だけを
検証し、Alpaca API toolは呼びません。

## Alpaca paper read-only

`get_alpaca_readonly_snapshot`は`alpaca-mcp-server==2.2.1`をstdio child processとして
起動し、次の5 toolだけを内部allowlistから呼びます。

- `get_account_info`
- `get_all_positions`
- `get_stock_bars`
- `get_stock_latest_trade`
- `get_option_chain`

official server側にorder/close/config更新toolが存在してもDSH modelへ登録されません。
credentialはDSH processの`ALPACA_API_KEY` / `ALPACA_SECRET_KEY`からchild processへだけ渡し、
設定・session・ledgerへ書きません。常に`ALPACA_PAPER_TRADE=true`、free data feedはstock
`iex` / option `indicative`です。
account ID、account number、user IDなどの識別子はmodel/sessionへ返す前にrecursiveに除去し、
外部文字列・配列・result全体にも上限を設けます。

現在のlocal環境にcredentialがない場合、toolはAPI接続前にfail-closedします。credentialを
追加した後、最初はこのread-only toolだけを実行し、paper account IDなどの不要な個人情報を
ログやcommitへ残さないでください。
