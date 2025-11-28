# PDFMathTranslate API Docker セットアップ

このドキュメントでは、Docker Composeを使用してPDFMathTranslateのAPIサーバーを起動する方法を説明します。

## 前提条件

- Docker と Docker Compose がインストールされていること
- 十分なディスク容量（モデルと依存関係のダウンロードに必要）

## クイックスタート

### 方法1: 起動スクリプトを使用（推奨）

```bash
./start-api.sh
```

### 方法2: Docker Composeを直接使用

```bash
docker-compose -f docker-compose.api.yml up -d --build
```

## サービス構成

このセットアップでは以下の3つのサービスが起動します：

1. **redis**: Redisサーバー（Celeryのブローカーと結果バックエンド）
2. **api**: Flask APIサーバー（ポート11008）
3. **worker**: Celeryワーカー（非同期翻訳処理）

## APIエンドポイント

APIサーバーが起動すると、以下のエンドポイントが利用可能になります：

### 翻訳タスクの作成

```bash
curl http://localhost:11008/v1/translate \
  -F "file=@example.pdf" \
  -F 'data={"lang_in":"en","lang_out":"zh","service":"google","thread":4}'
```

レスポンス例：
```json
{"id":"d9894125-2f4e-45ea-9d93-1a9068d2045a"}
```

### タスクの状態確認

```bash
curl http://localhost:11008/v1/translate/d9894125-2f4e-45ea-9d93-1a9068d2045a
```

進行中のレスポンス例：
```json
{"info":{"n":13,"total":506},"state":"PROGRESS"}
```

完了時のレスポンス例：
```json
{"state":"SUCCESS"}
```

### 単一言語PDFの取得

```bash
curl http://localhost:11008/v1/translate/d9894125-2f4e-45ea-9d93-1a9068d2045a/mono \
  --output example-mono.pdf
```

### バイリンガルPDFの取得

```bash
curl http://localhost:11008/v1/translate/d9894125-2f4e-45ea-9d93-1a9068d2045a/dual \
  --output example-dual.pdf
```

### タスクの削除

```bash
curl http://localhost:11008/v1/translate/d9894125-2f4e-45ea-9d93-1a9068d2045a -X DELETE
```

## ログの確認

### すべてのサービスのログ

```bash
docker-compose -f docker-compose.api.yml logs -f
```

### 特定のサービスのログ

```bash
# APIサーバーのログ
docker-compose -f docker-compose.api.yml logs -f api

# ワーカーのログ
docker-compose -f docker-compose.api.yml logs -f worker

# Redisのログ
docker-compose -f docker-compose.api.yml logs -f redis
```

## サービスの停止

```bash
docker-compose -f docker-compose.api.yml down
```

データを保持したまま停止する場合は、上記のコマンドで問題ありません（Redisのデータはボリュームに保存されます）。

データも含めて完全に削除する場合：

```bash
docker-compose -f docker-compose.api.yml down -v
```

## トラブルシューティング

### ポートが既に使用されている場合

`docker-compose.api.yml`の`ports`セクションを編集して、別のポートを使用してください。

### メモリ不足エラー

Docker Desktopの設定で、より多くのメモリを割り当ててください。

### ビルドエラー

キャッシュをクリアして再ビルド：

```bash
docker-compose -f docker-compose.api.yml build --no-cache
```

## 詳細情報

APIの詳細な使用方法については、[API Details](./docs/APIS.md)を参照してください。


