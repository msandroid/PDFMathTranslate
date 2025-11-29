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

**重要**: ワーカーサービスは**リポジトリからデプロイするサービス**として追加するだけでOKです。Redisなどの他のサービスを追加する必要はありません（既存のRedisサービスを共有します）。

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
   - **Name**: `CELERY_WORKER_CONCURRENCY`（推奨）
   - **Value**: `2`（デフォルト値）
     - Railwayなどのクラウド環境では、メモリ制限があるため`2`が推奨されます
     - より多くのメモリがある場合は、`4`や`8`に増やすことができます
     - デフォルト値（未設定時）は`2`です

**重要**: 
- APIサーバーとCeleryワーカーは**同じRedisインスタンス**に接続する必要があります
- 環境変数の値は、APIサーバーとCeleryワーカーで**完全に同じ**である必要があります
- Railwayの内部ネットワークでは、サービス名をホスト名として使用できます
- Redisサービスの「Settings」→「Networking」で内部ホスト名を確認できます
- **注意**: `redis.railway.internal`という形式は正しくありません。必ず`<service-name>.up.railway.internal`の形式を使用するか、サービス名を直接使用してください

#### サービス3: Redis（オプション、Railway Redisプラグインを使用する場合）

RailwayのRedisプラグインを使用するか、別のRedisサービスを使用できます。

1. Railwayダッシュボードで「New」→「Database」→「Add Redis」を選択
2. Redisサービスの内部URLを取得
3. 上記の`CELERY_BROKER`と`CELERY_RESULT`にそのURLを設定

### 3. 環境変数の設定

各サービスで以下の環境変数を設定します：

**APIサーバーサービス:**
```
CELERY_BROKER=redis://<redis-host>:6379/0
CELERY_RESULT=redis://<redis-host>:6379/0
```

**Celeryワーカーサービス:**
```
CELERY_BROKER=redis://<redis-host>:6379/0
CELERY_RESULT=redis://<redis-host>:6379/0
CELERY_WORKER_CONCURRENCY=2
```

**重要**: 
- Redisサービスの内部URLを使用してください。Railwayでは、サービス間の通信には内部URLを使用します。
- `CELERY_WORKER_CONCURRENCY`は、ワーカーが同時に処理するタスクの数を制御します。Railwayなどのクラウド環境では、メモリ制限があるため`2`が推奨されます。デフォルト値は`2`です（未設定時）。
- より多くのメモリがある場合は、`4`や`8`に増やすことができますが、メモリ不足で再起動が発生する可能性があります。

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

**重要**: `redis.railway.internal`という形式は正しくありません。必ず以下の方法で正しいホスト名を取得してください。

**方法1: Railwayダッシュボードから取得（推奨）**

1. RailwayダッシュボードでRedisサービスを開く
2. 「**Settings**」タブをクリック
3. 「**Networking**」セクションを開く
4. 「**Private Networking**」のホスト名を確認
   - 正しい形式の例: `redis-production.up.railway.internal`
   - または: `<service-name>.up.railway.internal`
5. このホスト名を使用して、環境変数の値を設定
   - 例: `redis://redis-production.up.railway.internal:6379/0`

**方法2: サービス名を使用（同じプロジェクト内の場合）**

同じRailwayプロジェクト内のサービス間では、サービス名を直接ホスト名として使用できる場合があります。

1. Redisサービスの名前を確認（例: `redis`、`redis-production`）
2. 環境変数に`redis://<service-name>:6379/0`を設定
   - 例: `redis://redis:6379/0`
   - 例: `redis://redis-production:6379/0`

**注意事項**:
- `redis.railway.internal`という形式は使用しないでください（動作しません）
- 必ず`redis://`で始まり、`:6379/0`で終わる形式にしてください
- ホスト名にポート番号を含めないでください（URLの形式で指定します）

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

### セキュリティ警告（root権限で実行）

**症状**:
- ログに以下のような警告が表示される：
  ```
  SecurityWarning: You're running the worker with superuser privileges: this is
  absolutely not recommended!
  Please specify a different user using the --uid option.
  User information: uid=0 euid=0 gid=0 egid=0
  ```

**原因**:
- Dockerコンテナ内でCeleryワーカーがroot権限（uid=0）で実行されている
- これはセキュリティ上の警告ですが、Dockerコンテナ内では一般的な動作です

**解決方法**:
- **この警告は無視して問題ありません**。Dockerコンテナ内では、root権限で実行されることが一般的です。
- Railwayなどのクラウド環境では、コンテナが分離されているため、セキュリティ上のリスクは低いです。
- 警告を抑制したい場合は、Celeryの設定で`worker_disable_rate_limits=True`を設定するか、環境変数で`CELERYD_FORCE_EXECV=true`を設定することもできますが、通常は必要ありません。

### ワーカーが定期的に再起動する

**症状**:
- ログを見ると、20秒ごと程度にワーカーが再起動しているように見える
- `concurrency: 48`などの高い並行度が設定されている

**原因**:
- デフォルトの並行度（concurrency）が高すぎて、メモリ不足が発生している
- Railwayなどのクラウド環境では、メモリ制限があるため、高い並行度は推奨されません

**解決方法**:
1. 環境変数`CELERY_WORKER_CONCURRENCY`を設定して、並行度を下げる：
   - **推奨値**: `2`（Railwayなどのクラウド環境）
   - **メモリに余裕がある場合**: `4`や`8`に増やすことも可能
2. ワーカーサービスの「Settings」→「Variables」で以下を追加：
   - **Name**: `CELERY_WORKER_CONCURRENCY`
   - **Value**: `2`
3. サービスを再デプロイして、ログを確認：
   - 再起動が止まり、安定して動作することを確認
   - ログに`concurrency: 2`と表示されることを確認

**注意**: 
- 並行度を上げすぎると、メモリ不足で再起動が発生する可能性があります
- Railwayの無料プランでは、メモリ制限が厳しいため、`2`が推奨されます

### Redis接続エラー

**症状**:
- ワーカーのログに`Connection refused`や`Name or service not known`などのエラーが表示される
- エラーメッセージ例: `Error -2 connecting to redis.railway.internal:6379. Name or service not known.`
- タスクが作成されても処理されない

**原因**:
- Redisサービスのホスト名が正しく設定されていない
- 環境変数に間違ったホスト名が設定されている
- Railwayの内部DNS名の形式が間違っている

**解決方法**:

1. **Redisサービスの確認**:
   - RailwayダッシュボードでRedisサービスが起動しているか確認
   - Redisサービスの「Logs」タブでエラーがないか確認

2. **正しいホスト名の取得方法**:
   
   **方法A: Railwayダッシュボードから取得（推奨）**
   
   1. RailwayダッシュボードでRedisサービスを開く
   2. 「**Settings**」タブをクリック
   3. 「**Networking**」セクションを開く
   4. 「**Private Networking**」のホスト名を確認
      - 正しい形式の例: `redis-production.up.railway.internal`
      - または: `<service-name>.up.railway.internal`
   5. このホスト名を使用して環境変数を設定
      - 例: `redis://redis-production.up.railway.internal:6379/0`
   
   **方法B: 環境変数から取得（推奨）**
   
   RailwayのRedisサービスでは、`REDIS_URL`という環境変数が自動的に設定される場合があります。
   
   **重要**: アプリケーションは以下の優先順位でRedis接続URLを決定します：
   1. `REDIS_URL`環境変数（最優先）
   2. `CELERY_BROKER`環境変数
   3. `REDISHOST`環境変数（`REDISPORT`、`REDISPASSWORD`、`REDISDB`と組み合わせ）
   4. `CELERY_RESULT`環境変数（フォールバック）
   5. デフォルト値（`redis://127.0.0.1:6379/0`）
   
   **推奨設定**:
   - RailwayのRedisサービスが`REDIS_URL`環境変数を自動設定する場合、それをそのまま使用できます
   - ワーカーサービスの「Settings」→「Variables」で`REDIS_URL`環境変数を確認
   - 存在する場合、`CELERY_BROKER`と`CELERY_RESULT`の両方に同じ値を設定
   
   **手動設定の場合**:
   1. Redisサービスの「Settings」→「Variables」を確認
   2. `REDIS_URL`または`REDISHOST`などの環境変数を確認
   3. その値からホスト名を抽出
   4. ワーカーサービスの`CELERY_BROKER`と`CELERY_RESULT`に設定
   
   **方法C: サービス名を使用（同じプロジェクト内の場合）**
   
   同じRailwayプロジェクト内のサービス間では、サービス名を直接ホスト名として使用できる場合があります。
   
   1. Redisサービスの名前を確認（例: `redis`、`redis-production`）
   2. 環境変数に`redis://<service-name>:6379/0`を設定
      - 例: `redis://redis:6379/0`
      - 例: `redis://redis-production:6379/0`
   
   **注意**: `redis.railway.internal`という形式は正しくありません。必ず上記の方法で正しいホスト名を取得してください。

3. **環境変数の確認と修正**:
   - ワーカーサービスの「Settings」→「Variables」で以下を確認：
     - `REDIS_URL`が設定されているか（最優先、Railwayが自動設定する場合がある）
     - `CELERY_BROKER`が設定されているか
     - `CELERY_RESULT`が設定されているか
     - 値の形式が正しいか（`redis://<host>:6379/0`）
   - **推奨**: `REDIS_URL`環境変数が存在する場合、それを`CELERY_BROKER`と`CELERY_RESULT`の両方に設定
   - **間違った例**: `redis://redis.railway.internal:6379/0`（この形式は動作しません）
   - **正しい例**: `redis://redis-production.up.railway.internal:6379/0`
   - または: `redis://redis:6379/0`（サービス名を使用する場合）
   - **注意**: `redis.up.railway.internal`のような不完全なホスト名はDNS解決に失敗する可能性があります。必ず完全なホスト名（`<service-name>.up.railway.internal`）を使用してください

4. **環境変数の更新手順**:
   1. ワーカーサービスの「Settings」→「Variables」を開く
   2. `CELERY_BROKER`と`CELERY_RESULT`の値を確認
   3. 上記の方法で取得した正しいホスト名を使用して値を更新
   4. 「Save」をクリック
   5. サービスが自動的に再デプロイされます
   6. 「Logs」タブで接続が成功したか確認

5. **接続テスト**:
   - ワーカーサービスのログで、Redisへの接続が成功しているか確認
   - 成功した場合、以下のようなログが表示されます：
     ```
     [INFO] celery@xxxxx ready.
     ```
   - 接続エラーが続く場合、ホスト名を再度確認して修正

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
   - **注意**: リポジトリからデプロイするサービスとして追加するだけでOKです
   - Redisなどの他のサービスを追加する必要はありません（既存のRedisを共有）
2. **Start Command**: `pdf2zh --celery worker --loglevel=info`
   - **注意**: `--loglevel`、`--concurrency`などのCeleryオプションは、`pdf2zh`コマンドが自動的にCeleryに渡します
3. **環境変数**:
   - `CELERY_BROKER`: `redis://<redis-host>:6379/0`（APIサーバーと同じ値）
   - `CELERY_RESULT`: `redis://<redis-host>:6379/0`（APIサーバーと同じ値）

**最小構成（Celeryオプションなし）**:
- Start Command: `pdf2zh --celery worker`
- これでも動作しますが、ログレベルはデフォルトになります

**Redisサービスについて**:
- Redisサービスが既に存在する場合（APIサーバー用に作成済み）: 追加不要、既存のRedisを共有
- Redisサービスが存在しない場合: 「+ New」→「Database」→「Add Redis」で追加が必要

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


