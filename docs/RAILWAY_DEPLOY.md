# Railway デプロイガイド

このドキュメントでは、RailwayでPDFMathTranslate APIをデプロイする方法を説明します。

## 前提条件

- Railwayアカウント
- GitHubリポジトリ（オプション、GitHub連携を使用する場合）

## デプロイ手順

### 1. プロジェクトの作成

1. Railwayダッシュボードで「New Project」をクリック
2. 「Deploy from GitHub repo」を選択（GitHub連携を使用する場合）
3. リポジトリを選択

### 2. サービスの設定

Railwayでは、**2つのサービス**を作成する必要があります：

#### サービス1: APIサーバー

1. サービス名: `api` または `pdf2zh-api`
2. **Start Command**: `pdf2zh --flask`
3. **環境変数**:
   - `PORT`: `11008`（Railwayが自動的に設定する場合もあります）
   - `CELERY_BROKER`: `redis://<redis-service-url>:6379/0`
   - `CELERY_RESULT`: `redis://<redis-service-url>:6379/0`

#### サービス2: Celeryワーカー（重要）

**既存のプロジェクトにワーカーサービスを追加する場合:**

1. Railwayダッシュボードで、既存のプロジェクトを開く
2. プロジェクト画面の右上にある「**+ New**」ボタンをクリック
3. ドロップダウンメニューから「**Service**」を選択
4. 「**Deploy from GitHub repo**」を選択（既にGitHub連携している場合）
   - または「**Empty Service**」を選択して手動で設定
5. 同じリポジトリを選択（APIサーバーと同じリポジトリ）
6. サービスが作成されたら、サービス名をクリックして設定画面を開く

**ワーカーサービスの設定:**

1. サービス画面の「**Settings**」タブをクリック
2. 「**Deploy**」セクションを開く
3. 「**Start Command**」フィールドに以下を入力：
   ```
   pdf2zh --celery worker --loglevel=info
   ```
   
   **注意**: `--loglevel`と`--concurrency`などのCelery固有のオプションは、`pdf2zh`コマンドが自動的にCeleryに渡します。
4. 「**Save**」ボタンをクリック

**環境変数の設定:**

1. 同じ「**Settings**」タブで「**Variables**」セクションを開く
2. 「**+ New Variable**」をクリック
3. 以下の環境変数を追加（APIサーバーと同じ値を使用）：
   - **Name**: `CELERY_BROKER`
   - **Value**: `redis://<redis-host>:6379/0`
     - `<redis-host>`は、RailwayのRedisサービスの内部ホスト名
     - 例: `redis://redis-production.up.railway.internal:6379/0`
   - **Name**: `CELERY_RESULT`
   - **Value**: `redis://<redis-host>:6379/0`（CELERY_BROKERと同じ値）

**重要**: 
- APIサーバーとCeleryワーカーは**同じRedisインスタンス**に接続する必要があります
- Railwayの内部ネットワークでは、サービス名をホスト名として使用できます
- Redisサービスの「Settings」→「Networking」で内部ホスト名を確認できます

#### サービス3: Redis（オプション、Railway Redisプラグインを使用する場合）

RailwayのRedisプラグインを使用するか、別のRedisサービスを使用できます。

1. Railwayダッシュボードで「New」→「Database」→「Add Redis」を選択
2. Redisサービスの内部URLを取得
3. 上記の`CELERY_BROKER`と`CELERY_RESULT`にそのURLを設定

### 3. 環境変数の設定

各サービスで以下の環境変数を設定します：

```
CELERY_BROKER=redis://<redis-host>:6379/0
CELERY_RESULT=redis://<redis-host>:6379/0
```

**重要**: Redisサービスの内部URLを使用してください。Railwayでは、サービス間の通信には内部URLを使用します。

### 4. Celeryワーカーサービスの確認

ワーカーサービスが正しく起動しているか確認する方法：

#### 方法1: Railwayダッシュボードで確認

1. ワーカーサービスの画面を開く
2. 「**Logs**」タブをクリック
3. 以下のようなログが表示されていれば正常に起動しています：
   ```
   [INFO] celery@xxxxx ready.
   ```
   または
   ```
   celery@xxxxx v5.x.x (singularity)
   ```

#### 方法2: コマンドで確認

APIサーバーからワーカーの状態を確認するには、ヘルスチェックエンドポイントを使用します：

```bash
curl https://<your-railway-app-url>/health
```

正常な場合、以下のレスポンスが返されます：

```json
{"status":"ok","service":"pdf2zh-api"}
```

#### 方法3: 翻訳タスクで確認

1. 翻訳タスクを作成
2. タスクIDを取得
3. ステータスを確認：
   ```bash
   curl https://<your-railway-app-url>/v1/translate/<task-id>
   ```
4. ワーカーが動作している場合、ステータスが`PROGRESS`または`SUCCESS`に変わります
5. ワーカーが動作していない場合、ステータスは`PENDING`のままです

### 5. デプロイの確認

デプロイ後、以下のコマンドでヘルスチェックを実行します：

```bash
curl https://<your-railway-app-url>/health
```

正常な場合、以下のレスポンスが返されます：

```json
{"status":"ok","service":"pdf2zh-api"}
```

## Celeryワーカーサービスの作成手順（詳細）

### ステップ1: サービスを追加

1. Railwayダッシュボードにログイン
2. プロジェクト一覧から、PDFMathTranslateプロジェクトを選択
3. プロジェクト画面の右上にある「**+ New**」ボタンをクリック
4. 「**Service**」を選択
5. 「**Deploy from GitHub repo**」を選択
6. 既に接続されているリポジトリを選択（APIサーバーと同じリポジトリ）

### ステップ2: サービス名を設定

1. 作成されたサービスをクリック
2. サービス名を`worker`または`pdf2zh-worker`に変更（任意）
3. 変更は自動的に保存されます

### ステップ3: Start Commandを設定

1. サービス画面で「**Settings**」タブをクリック
2. 「**Deploy**」セクションを開く
3. 「**Start Command**」フィールドを見つける
4. 以下のコマンドを入力：
   ```
   pdf2zh --celery worker --loglevel=info
   ```
5. 「**Save**」ボタンをクリック

**注意**: Start Commandを設定しないと、デフォルトのコマンドが実行され、Celeryワーカーが起動しません。

### ステップ4: 環境変数を設定

1. 同じ「**Settings**」タブで「**Variables**」セクションを開く
2. 「**+ New Variable**」ボタンをクリック
3. 以下の環境変数を追加：

   **変数1: CELERY_BROKER**
   - **Name**: `CELERY_BROKER`
   - **Value**: `redis://<redis-host>:6379/0`
   - **説明**: Celeryがタスクをキューに追加するためのRedis接続URL

   **変数2: CELERY_RESULT**
   - **Name**: `CELERY_RESULT`
   - **Value**: `redis://<redis-host>:6379/0`（CELERY_BROKERと同じ値）
   - **説明**: Celeryがタスクの結果を保存するためのRedis接続URL

**Redisホスト名の取得方法:**

1. RailwayダッシュボードでRedisサービスを開く
2. 「**Settings**」タブをクリック
3. 「**Networking**」セクションを開く
4. 「**Private Networking**」のホスト名を確認
   - 例: `redis-production.up.railway.internal`
5. このホスト名を使用して、環境変数の値を設定
   - 例: `redis://redis-production.up.railway.internal:6379/0`

**重要**: 
- APIサーバーとCeleryワーカーは**同じRedisインスタンス**を使用する必要があります
- 環境変数の値は、APIサーバーとCeleryワーカーで**完全に同じ**である必要があります

### ステップ5: デプロイと確認

1. 設定を保存すると、自動的にデプロイが開始されます
2. 「**Deployments**」タブでデプロイの進行状況を確認
3. デプロイが完了したら、「**Logs**」タブを開く
4. 以下のようなログが表示されていれば成功：
   ```
   [INFO] celery@xxxxx ready.
   ```

### ステップ6: 動作確認

1. APIサーバーから翻訳タスクを作成
2. ワーカーサービスの「**Logs**」タブを確認
3. 以下のようなログが表示されれば、タスクが処理されています：
   ```
   DEBUG [Celery Worker]: translate_task started, task_id=...
   ```

## トラブルシューティング

### タスクがPENDINGのままになる

この問題は、**Celeryワーカーが起動していない**ことが原因です。

**確認手順**:

1. Railwayダッシュボードで、Celeryワーカーサービスが作成されているか確認
2. ワーカーサービスの「**Logs**」タブを開く
3. エラーメッセージがないか確認

**よくある原因と解決方法**:

- **原因1: Start Commandが設定されていない**
  - **解決方法**: 「Settings」→「Deploy」→「Start Command」に`pdf2zh --celery worker --loglevel=info`を設定

- **原因2: 環境変数が設定されていない**
  - **解決方法**: 「Settings」→「Variables」で`CELERY_BROKER`と`CELERY_RESULT`を設定

- **原因3: Redis接続エラー**
  - **解決方法**: 
    - Redisサービスのホスト名が正しいか確認
    - 環境変数の値が正しいか確認（`redis://`で始まり、`:6379/0`で終わる）
    - APIサーバーとワーカーで同じRedisインスタンスを使用しているか確認

- **原因4: ワーカーサービスが起動していない**
  - **解決方法**: 
    - ワーカーサービスの「Deployments」タブで、最新のデプロイが成功しているか確認
    - エラーがある場合は、ログを確認して修正

- **原因5: コマンド引数のエラー（`unrecognized arguments`）**
  - **症状**: ログに`pdf2zh: error: unrecognized arguments: --loglevel=info --concurrency=2`が表示される
  - **原因**: 古いバージョンのコードでは、Celery固有の引数が認識されない
  - **解決方法**: 
    - 最新のコードに更新してください（この問題は修正済みです）
    - または、Start Commandを`pdf2zh --celery worker`のみにして、Celeryのオプションは環境変数で設定

### Redis接続エラー

**症状**:
- ワーカーのログに`Connection refused`や`Name or service not known`などのエラーが表示される
- タスクが作成されても処理されない

**解決方法**:

1. **Redisサービスの確認**:
   - RailwayダッシュボードでRedisサービスが起動しているか確認
   - Redisサービスの「Logs」タブでエラーがないか確認

2. **環境変数の確認**:
   - ワーカーサービスの「Settings」→「Variables」で以下を確認：
     - `CELERY_BROKER`が設定されているか
     - `CELERY_RESULT`が設定されているか
     - 値の形式が正しいか（`redis://<host>:6379/0`）

3. **ホスト名の確認**:
   - Redisサービスの「Settings」→「Networking」で内部ホスト名を確認
   - 環境変数の値にこのホスト名が含まれているか確認
   - Railwayの内部ネットワークでは、サービス名をホスト名として使用できます

4. **接続テスト**:
   - ワーカーサービスのログで、Redisへの接続が成功しているか確認
   - 接続エラーがある場合、環境変数の値を修正して再デプロイ

### メモリ不足エラー

**症状**:
- ワーカーのログに`MemoryError`や`Killed`などのメッセージが表示される
- タスクが途中で失敗する

**解決方法**:

1. **Railwayプランの確認**:
   - Railwayのプランで利用可能なメモリを確認
   - 必要に応じてプランをアップグレード

2. **ワーカーサービスの設定**:
   - ワーカーサービスの「Settings」→「Resources」でメモリ制限を確認
   - 可能であれば、メモリ制限を増やす

3. **同時実行数の制限**:
   - Celeryワーカーの同時実行数を制限することで、メモリ使用量を減らせます
   - Start Commandを以下に変更：
     ```
     pdf2zh --celery worker --loglevel=info --concurrency=1
     ```
   - **注意**: `--concurrency`オプションはCeleryに直接渡されます

### ワーカーがタスクを処理しない

**症状**:
- ワーカーは起動しているが、タスクが処理されない
- ログにエラーが表示されない

**解決方法**:

1. **タスクの確認**:
   - APIサーバーのログで、タスクが正しく作成されているか確認
   - タスクIDが返されているか確認

2. **Redis接続の確認**:
   - APIサーバーとワーカーが同じRedisインスタンスに接続しているか確認
   - 環境変数の値が完全に同じか確認

3. **ワーカーのログ確認**:
   - ワーカーサービスの「Logs」タブで、タスクを受信しているか確認
   - `Received task`のようなメッセージが表示されるか確認

4. **再デプロイ**:
   - ワーカーサービスを再デプロイしてみる
   - 「Deployments」タブで「Redeploy」をクリック

## Railwayでのサービス構成

Railwayプロジェクトは以下のような構成になります：

```
Railway Project
├── api (Flask APIサーバー)
│   └── Start Command: pdf2zh --flask
├── worker (Celeryワーカー)
│   └── Start Command: pdf2zh --celery worker --loglevel=info
└── redis (Redisデータベース)
    └── Railway Redisプラグインまたは外部Redisサービス
```

## 注意事項

1. **Celeryワーカーは必須**: APIサーバーだけでは翻訳タスクは処理されません。必ずCeleryワーカーサービスも作成してください。

2. **Redis接続**: APIサーバーとCeleryワーカーは、同じRedisインスタンスに接続する必要があります。

3. **ログの確認**: 問題が発生した場合は、各サービスのログを確認してください。Railwayダッシュボードの「Logs」タブから確認できます。

4. **環境変数**: 環境変数は各サービスで個別に設定する必要があります。

## クイックリファレンス

### Celeryワーカーサービスの最小設定

既存のプロジェクトにワーカーサービスを追加する場合の最小設定：

1. **サービス追加**: 「+ New」→「Service」→ 同じリポジトリを選択
2. **Start Command**: `pdf2zh --celery worker --loglevel=info`
   - **注意**: `--loglevel`、`--concurrency`などのCeleryオプションは、`pdf2zh`コマンドが自動的にCeleryに渡します
3. **環境変数**:
   - `CELERY_BROKER`: `redis://<redis-host>:6379/0`
   - `CELERY_RESULT`: `redis://<redis-host>:6379/0`

**最小構成（Celeryオプションなし）**:
- Start Command: `pdf2zh --celery worker`
- これでも動作しますが、ログレベルはデフォルトになります

### 確認チェックリスト

- [ ] ワーカーサービスが作成されている
- [ ] Start Commandが正しく設定されている
- [ ] 環境変数`CELERY_BROKER`が設定されている
- [ ] 環境変数`CELERY_RESULT`が設定されている
- [ ] 環境変数の値がAPIサーバーと同じである
- [ ] ワーカーサービスのログに`celery@xxxxx ready`が表示されている
- [ ] 翻訳タスクを作成した際、ワーカーのログにタスク処理のメッセージが表示される

### よくある間違い

1. **Start Commandを設定していない**
   - デフォルトではCeleryワーカーが起動しません
   - 必ず`pdf2zh --celery worker --loglevel=info`を設定してください

2. **環境変数を設定していない**
   - `CELERY_BROKER`と`CELERY_RESULT`の両方が必要です
   - どちらか一方だけでは動作しません

3. **APIサーバーとワーカーで異なるRedisを使用している**
   - 両方のサービスは同じRedisインスタンスに接続する必要があります
   - 環境変数の値が完全に同じであることを確認してください

4. **Redisホスト名が間違っている**
   - Railwayの内部ネットワークでは、サービス名をホスト名として使用できます
   - 外部URLではなく、内部ホスト名を使用してください

## 参考リンク

- [Railway Documentation](https://docs.railway.app/)
- [Celery Documentation](https://docs.celeryq.dev/)
- [Railway Networking](https://docs.railway.app/networking/private-networking)

