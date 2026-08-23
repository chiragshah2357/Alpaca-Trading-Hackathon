# DSH local harness

このbundleは既存のdeterministic risk engineをDSHの単一agentへ接続します。
モデルに公開するtoolは次の2つだけです。

- `get_decision_context`: risk snapshotと選択可能な候補を取得
- `submit_decision`: 候補を1つ選び、deterministic gateで検証してpaper dry-runを記録

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
npm run test:profile
cd ../..
python3 -m unittest discover -s tests -v
```

`test:profile`は一時ディレクトリ内にDSH_HOMEとdry-run ledgerを作成します。
実account、remote model、paper orderには接続しません。
