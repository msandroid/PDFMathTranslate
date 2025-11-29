# PDFMathTranslate API - Swift 使用ガイド

このドキュメントでは、SwiftアプリケーションからPDFMathTranslate APIを使用する方法を説明します。

## 目次

- [基本情報](#基本情報)
- [データモデル](#データモデル)
- [APIクライアントの実装](#apiクライアントの実装)
- [使用例](#使用例)
- [SwiftUIでの使用例](#swiftuiでの使用例)
- [エラーハンドリング](#エラーハンドリング)
- [注意事項](#注意事項)

---

## 基本情報

### API ベースURL

```
https://pdfmathtranslate-production-cf37.up.railway.app
```

### エンドポイント一覧

| メソッド | エンドポイント | 説明 |
|---------|--------------|------|
| GET | `/health` | ヘルスチェック |
| POST | `/v1/translate` | 翻訳タスクの作成 |
| GET | `/v1/translate/{id}` | タスクステータスの確認 |
| GET | `/v1/translate/{id}/mono` | 単一言語PDFの取得 |
| GET | `/v1/translate/{id}/dual` | バイリンガルPDFの取得 |
| DELETE | `/v1/translate/{id}` | タスクの削除 |

---

## データモデル

まず、APIで使用するデータモデルを定義します。

```swift
import Foundation

// MARK: - 翻訳設定
struct TranslateOptions: Codable {
    let langIn: String      // 入力言語コード（例: "en", "ja", "zh"）
    let langOut: String     // 出力言語コード（例: "zh", "en", "ja"）
    let service: String     // 翻訳サービス（例: "google", "deepl", "openai"）
    let thread: Int         // スレッド数（デフォルト: 4）
    
    enum CodingKeys: String, CodingKey {
        case langIn = "lang_in"
        case langOut = "lang_out"
        case service
        case thread
    }
    
    init(langIn: String = "en", langOut: String = "zh", service: String = "google", thread: Int = 4) {
        self.langIn = langIn
        self.langOut = langOut
        self.service = service
        self.thread = thread
    }
}

// MARK: - タスク作成レスポンス
struct TaskResponse: Codable {
    let id: String
}

// MARK: - タスクステータス
struct TaskStatus: Codable {
    let state: String           // "PROGRESS", "SUCCESS", "FAILURE", "PENDING"
    let info: ProgressInfo?     // 進捗情報（stateがPROGRESSの場合）
}

struct ProgressInfo: Codable {
    let n: Int          // 現在のページ数
    let total: Int      // 総ページ数
}

// MARK: - PDF形式
enum PDFFormat: String {
    case mono = "mono"  // 単一言語PDF
    case dual = "dual"  // バイリンガルPDF
}

// MARK: - APIエラー
enum APIError: Error, LocalizedError {
    case invalidURL
    case encodingError
    case serverError(String)
    case taskNotReady
    case taskFailed
    case networkError(Error)
    
    var errorDescription: String? {
        switch self {
        case .invalidURL:
            return "無効なURLです"
        case .encodingError:
            return "データのエンコードに失敗しました"
        case .serverError(let message):
            return "サーバーエラー: \(message)"
        case .taskNotReady:
            return "タスクがまだ準備できていません"
        case .taskFailed:
            return "翻訳タスクが失敗しました"
        case .networkError(let error):
            return "ネットワークエラー: \(error.localizedDescription)"
        }
    }
}
```

---

## APIクライアントの実装

APIクライアントクラスを実装します。

```swift
import Foundation

class PDFTranslateAPIClient {
    private let baseURL: String
    private let session: URLSession
    
    init(baseURL: String, session: URLSession = .shared) {
        self.baseURL = baseURL
        self.session = session
    }
    
    // MARK: - ヘルスチェック
    func healthCheck() async throws -> Bool {
        guard let url = URL(string: "\(baseURL)/health") else {
            throw APIError.invalidURL
        }
        
        do {
            let (_, response) = try await session.data(from: url)
            guard let httpResponse = response as? HTTPURLResponse,
                  httpResponse.statusCode == 200 else {
                return false
            }
            return true
        } catch {
            throw APIError.networkError(error)
        }
    }
    
    // MARK: - 翻訳タスクの作成
    func createTranslateTask(
        pdfData: Data,
        options: TranslateOptions
    ) async throws -> String {
        guard let url = URL(string: "\(baseURL)/v1/translate") else {
            throw APIError.invalidURL
        }
        
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        
        // multipart/form-data の作成
        let boundary = UUID().uuidString
        request.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")
        
        var body = Data()
        
        // ファイルパート
        body.append("--\(boundary)\r\n".data(using: .utf8)!)
        body.append("Content-Disposition: form-data; name=\"file\"; filename=\"document.pdf\"\r\n".data(using: .utf8)!)
        body.append("Content-Type: application/pdf\r\n\r\n".data(using: .utf8)!)
        body.append(pdfData)
        body.append("\r\n".data(using: .utf8)!)
        
        // dataパート (JSON文字列)
        let encoder = JSONEncoder()
        guard let jsonData = try? encoder.encode(options),
              let jsonString = String(data: jsonData, encoding: .utf8) else {
            throw APIError.encodingError
        }
        
        body.append("--\(boundary)\r\n".data(using: .utf8)!)
        body.append("Content-Disposition: form-data; name=\"data\"\r\n\r\n".data(using: .utf8)!)
        body.append(jsonString.data(using: .utf8)!)
        body.append("\r\n".data(using: .utf8)!)
        
        body.append("--\(boundary)--\r\n".data(using: .utf8)!)
        
        request.httpBody = body
        
        do {
            let (data, response) = try await session.data(for: request)
            
            guard let httpResponse = response as? HTTPURLResponse else {
                throw APIError.serverError("Invalid response")
            }
            
            guard httpResponse.statusCode == 200 else {
                let errorMessage = String(data: data, encoding: .utf8) ?? "Unknown error"
                throw APIError.serverError("HTTP \(httpResponse.statusCode): \(errorMessage)")
            }
            
            let decoder = JSONDecoder()
            let taskResponse = try decoder.decode(TaskResponse.self, from: data)
            return taskResponse.id
        } catch let error as DecodingError {
            throw APIError.encodingError
        } catch let error as APIError {
            throw error
        } catch {
            throw APIError.networkError(error)
        }
    }
    
    // MARK: - タスクステータスの確認
    func checkTaskStatus(taskId: String) async throws -> TaskStatus {
        guard let url = URL(string: "\(baseURL)/v1/translate/\(taskId)") else {
            throw APIError.invalidURL
        }
        
        do {
            let (data, response) = try await session.data(from: url)
            
            guard let httpResponse = response as? HTTPURLResponse else {
                throw APIError.serverError("Invalid response")
            }
            
            guard httpResponse.statusCode == 200 else {
                let errorMessage = String(data: data, encoding: .utf8) ?? "Unknown error"
                throw APIError.serverError("HTTP \(httpResponse.statusCode): \(errorMessage)")
            }
            
            let decoder = JSONDecoder()
            return try decoder.decode(TaskStatus.self, from: data)
        } catch let error as DecodingError {
            throw APIError.encodingError
        } catch let error as APIError {
            throw error
        } catch {
            throw APIError.networkError(error)
        }
    }
    
    // MARK: - 翻訳済みPDFのダウンロード
    func downloadTranslatedPDF(taskId: String, format: PDFFormat) async throws -> Data {
        guard let url = URL(string: "\(baseURL)/v1/translate/\(taskId)/\(format.rawValue)") else {
            throw APIError.invalidURL
        }
        
        do {
            let (data, response) = try await session.data(from: url)
            
            guard let httpResponse = response as? HTTPURLResponse else {
                throw APIError.serverError("Invalid response")
            }
            
            guard httpResponse.statusCode == 200 else {
                if httpResponse.statusCode == 400 {
                    throw APIError.taskNotReady
                }
                let errorMessage = String(data: data, encoding: .utf8) ?? "Unknown error"
                throw APIError.serverError("HTTP \(httpResponse.statusCode): \(errorMessage)")
            }
            
            return data
        } catch let error as APIError {
            throw error
        } catch {
            throw APIError.networkError(error)
        }
    }
    
    // MARK: - タスクの削除
    func deleteTask(taskId: String) async throws {
        guard let url = URL(string: "\(baseURL)/v1/translate/\(taskId)") else {
            throw APIError.invalidURL
        }
        
        var request = URLRequest(url: url)
        request.httpMethod = "DELETE"
        
        do {
            let (_, response) = try await session.data(for: request)
            
            guard let httpResponse = response as? HTTPURLResponse,
                  (200...299).contains(httpResponse.statusCode) else {
                throw APIError.serverError("Failed to delete task")
            }
        } catch let error as APIError {
            throw error
        } catch {
            throw APIError.networkError(error)
        }
    }
}
```

---

## 使用例

### 基本的な使用例

```swift
import Foundation

// APIクライアントの初期化
let apiClient = PDFTranslateAPIClient(
    baseURL: "https://pdfmathtranslate-production-cf37.up.railway.app"
)

// PDFファイルの読み込み
guard let pdfURL = Bundle.main.url(forResource: "example", withExtension: "pdf"),
      let pdfData = try? Data(contentsOf: pdfURL) else {
    print("PDFファイルが見つかりません")
    return
}

// 翻訳オプションの設定
let options = TranslateOptions(
    langIn: "en",
    langOut: "zh",
    service: "google",
    thread: 4
)

Task {
    do {
        // 1. タスクを作成
        print("翻訳タスクを作成中...")
        let taskId = try await apiClient.createTranslateTask(
            pdfData: pdfData,
            options: options
        )
        print("タスクID: \(taskId)")
        
        // 2. 状態をポーリング
        print("翻訳を開始...")
        while true {
            let status = try await apiClient.checkTaskStatus(taskId: taskId)
            
            if status.state == "PROGRESS", let info = status.info {
                print("進捗: \(info.n)/\(info.total) ページ")
            } else if status.state == "SUCCESS" {
                print("翻訳完了!")
                break
            } else if status.state == "FAILURE" {
                throw APIError.taskFailed
            }
            
            // 2秒待機
            try await Task.sleep(nanoseconds: 2_000_000_000)
        }
        
        // 3. PDFをダウンロード
        print("翻訳済みPDFをダウンロード中...")
        let translatedPDF = try await apiClient.downloadTranslatedPDF(
            taskId: taskId,
            format: .dual
        )
        
        // 4. ファイルに保存
        let documentsPath = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
        let outputURL = documentsPath.appendingPathComponent("translated.pdf")
        try translatedPDF.write(to: outputURL)
        print("保存完了: \(outputURL.path)")
        
    } catch {
        print("エラー: \(error.localizedDescription)")
    }
}
```

### ヘルスチェックの例

```swift
Task {
    do {
        let isHealthy = try await apiClient.healthCheck()
        if isHealthy {
            print("APIサーバーは正常に動作しています")
        } else {
            print("APIサーバーに問題があります")
        }
    } catch {
        print("ヘルスチェックエラー: \(error.localizedDescription)")
    }
}
```

---

## SwiftUIでの使用例

SwiftUIアプリでの実装例です。

### ViewModelの実装

```swift
import Foundation
import SwiftUI

@MainActor
class TranslateViewModel: ObservableObject {
    @Published var isTranslating = false
    @Published var currentPage = 0
    @Published var totalPages = 0
    @Published var translatedPDF: Data?
    @Published var errorMessage: String?
    @Published var taskId: String?
    
    private let apiClient = PDFTranslateAPIClient(
        baseURL: "https://pdfmathtranslate-production-cf37.up.railway.app"
    )
    
    // 翻訳を実行
    func translatePDF(_ pdfData: Data, options: TranslateOptions) {
        isTranslating = true
        errorMessage = nil
        currentPage = 0
        totalPages = 0
        translatedPDF = nil
        taskId = nil
        
        Task {
            do {
                // 1. タスクを作成
                let taskId = try await apiClient.createTranslateTask(
                    pdfData: pdfData,
                    options: options
                )
                self.taskId = taskId
                
                // 2. 状態をポーリング
                while true {
                    let status = try await apiClient.checkTaskStatus(taskId: taskId)
                    
                    if status.state == "PROGRESS", let info = status.info {
                        self.currentPage = info.n
                        self.totalPages = info.total
                    } else if status.state == "SUCCESS" {
                        // 3. PDFをダウンロード
                        let pdfData = try await apiClient.downloadTranslatedPDF(
                            taskId: taskId,
                            format: .dual
                        )
                        self.translatedPDF = pdfData
                        self.isTranslating = false
                        break
                    } else if status.state == "FAILURE" {
                        throw APIError.taskFailed
                    }
                    
                    // 2秒待機
                    try await Task.sleep(nanoseconds: 2_000_000_000)
                }
            } catch {
                self.errorMessage = error.localizedDescription
                self.isTranslating = false
            }
        }
    }
    
    // タスクをキャンセル
    func cancelTask() {
        guard let taskId = taskId else { return }
        
        Task {
            do {
                try await apiClient.deleteTask(taskId: taskId)
                self.taskId = nil
                self.isTranslating = false
            } catch {
                self.errorMessage = "キャンセルに失敗しました: \(error.localizedDescription)"
            }
        }
    }
}
```

### SwiftUI Viewの実装

```swift
import SwiftUI

struct TranslateView: View {
    @StateObject private var viewModel = TranslateViewModel()
    @State private var selectedPDFURL: URL?
    @State private var showFilePicker = false
    @State private var showSaveSheet = false
    
    var body: some View {
        NavigationView {
            VStack(spacing: 20) {
                // PDFファイル選択ボタン
                Button(action: {
                    showFilePicker = true
                }) {
                    Label("PDFファイルを選択", systemImage: "doc.fill")
                        .frame(maxWidth: .infinity)
                        .padding()
                        .background(Color.blue)
                        .foregroundColor(.white)
                        .cornerRadius(10)
                }
                .fileImporter(
                    isPresented: $showFilePicker,
                    allowedContentTypes: [.pdf],
                    allowsMultipleSelection: false
                ) { result in
                    handleFileSelection(result)
                }
                
                // 翻訳オプション
                if selectedPDFURL != nil {
                    VStack(alignment: .leading, spacing: 10) {
                        Text("翻訳オプション")
                            .font(.headline)
                        
                        // ここに言語選択などのUIを追加できます
                    }
                    .padding()
                    .background(Color.gray.opacity(0.1))
                    .cornerRadius(10)
                    
                    // 翻訳開始ボタン
                    Button(action: {
                        startTranslation()
                    }) {
                        Label("翻訳を開始", systemImage: "arrow.right.circle.fill")
                            .frame(maxWidth: .infinity)
                            .padding()
                            .background(viewModel.isTranslating ? Color.gray : Color.green)
                            .foregroundColor(.white)
                            .cornerRadius(10)
                    }
                    .disabled(viewModel.isTranslating)
                }
                
                // 進捗表示
                if viewModel.isTranslating {
                    VStack(spacing: 10) {
                        ProgressView()
                        if viewModel.totalPages > 0 {
                            Text("翻訳中... \(viewModel.currentPage)/\(viewModel.totalPages) ページ")
                                .font(.caption)
                            ProgressView(value: Double(viewModel.currentPage), total: Double(viewModel.totalPages))
                        } else {
                            Text("翻訳を開始しています...")
                                .font(.caption)
                        }
                        
                        Button("キャンセル", role: .destructive) {
                            viewModel.cancelTask()
                        }
                        .buttonStyle(.bordered)
                    }
                    .padding()
                    .background(Color.blue.opacity(0.1))
                    .cornerRadius(10)
                }
                
                // エラーメッセージ
                if let errorMessage = viewModel.errorMessage {
                    Text(errorMessage)
                        .foregroundColor(.red)
                        .padding()
                        .background(Color.red.opacity(0.1))
                        .cornerRadius(10)
                }
                
                // 翻訳済みPDF
                if let pdfData = viewModel.translatedPDF {
                    Button(action: {
                        showSaveSheet = true
                    }) {
                        Label("翻訳済みPDFを保存", systemImage: "square.and.arrow.down")
                            .frame(maxWidth: .infinity)
                            .padding()
                            .background(Color.purple)
                            .foregroundColor(.white)
                            .cornerRadius(10)
                    }
                    .sheet(isPresented: $showSaveSheet) {
                        ShareSheet(items: [pdfData])
                    }
                }
                
                Spacer()
            }
            .padding()
            .navigationTitle("PDF翻訳")
        }
    }
    
    private func handleFileSelection(_ result: Result<[URL], Error>) {
        switch result {
        case .success(let urls):
            if let url = urls.first {
                selectedPDFURL = url
            }
        case .failure(let error):
            viewModel.errorMessage = "ファイル選択エラー: \(error.localizedDescription)"
        }
    }
    
    private func startTranslation() {
        guard let pdfURL = selectedPDFURL,
              let pdfData = try? Data(contentsOf: pdfURL) else {
            viewModel.errorMessage = "PDFファイルを読み込めませんでした"
            return
        }
        
        let options = TranslateOptions(
            langIn: "en",
            langOut: "zh",
            service: "google",
            thread: 4
        )
        
        viewModel.translatePDF(pdfData, options: options)
    }
}

// ShareSheet（保存用）
struct ShareSheet: UIViewControllerRepresentable {
    let items: [Any]
    
    func makeUIViewController(context: Context) -> UIActivityViewController {
        let controller = UIActivityViewController(activityItems: items, applicationActivities: nil)
        return controller
    }
    
    func updateUIViewController(_ uiViewController: UIActivityViewController, context: Context) {}
}
```

---

## エラーハンドリング

エラーハンドリングの詳細な実装例です。

```swift
enum APIError: Error, LocalizedError {
    case invalidURL
    case encodingError
    case serverError(String)
    case taskNotReady
    case taskFailed
    case networkError(Error)
    case timeout
    
    var errorDescription: String? {
        switch self {
        case .invalidURL:
            return "無効なURLです"
        case .encodingError:
            return "データのエンコードに失敗しました"
        case .serverError(let message):
            return "サーバーエラー: \(message)"
        case .taskNotReady:
            return "タスクがまだ準備できていません"
        case .taskFailed:
            return "翻訳タスクが失敗しました"
        case .networkError(let error):
            return "ネットワークエラー: \(error.localizedDescription)"
        case .timeout:
            return "タイムアウトしました"
        }
    }
    
    var recoverySuggestion: String? {
        switch self {
        case .networkError:
            return "ネットワーク接続を確認してください"
        case .serverError:
            return "しばらく待ってから再度お試しください"
        case .timeout:
            return "処理に時間がかかっています。しばらく待ってから再度お試しください"
        default:
            return "アプリを再起動して再度お試しください"
        }
    }
}

// 使用例
Task {
    do {
        let taskId = try await apiClient.createTranslateTask(pdfData: data, options: options)
        // ...
    } catch let error as APIError {
        switch error {
        case .networkError:
            // ネットワークエラー時の処理
            print("ネットワークエラーが発生しました")
        case .taskFailed:
            // タスク失敗時の処理
            print("翻訳が失敗しました")
        default:
            print("エラー: \(error.localizedDescription)")
        }
        
        if let suggestion = error.recoverySuggestion {
            print("対処方法: \(suggestion)")
        }
    } catch {
        print("予期しないエラー: \(error.localizedDescription)")
    }
}
```

### タイムアウト処理の追加

長時間実行されるタスクに対してタイムアウトを設定する例です。

```swift
extension PDFTranslateAPIClient {
    func translatePDF(
        pdfData: Data,
        options: TranslateOptions,
        timeout: TimeInterval = 300 // 5分
    ) async throws -> Data {
        // 1. タスク作成
        let taskId = try await createTranslateTask(
            pdfData: pdfData,
            options: options
        )
        
        // 2. ステータス確認（タイムアウト付き）
        let startTime = Date()
        
        while Date().timeIntervalSince(startTime) < timeout {
            let status = try await checkTaskStatus(taskId: taskId)
            
            switch status.state {
            case "SUCCESS":
                // 3. PDFダウンロード
                return try await downloadTranslatedPDF(
                    taskId: taskId,
                    format: .dual
                )
            case "FAILURE":
                throw APIError.taskFailed
            case "PROGRESS":
                // 2秒待機してから再確認
                try await Task.sleep(nanoseconds: 2_000_000_000)
                continue
            default:
                throw APIError.serverError("Unknown task state: \(status.state)")
            }
        }
        
        throw APIError.timeout
    }
}
```

---

## 翻訳可能な言語について

### サポート言語数

PDFMathTranslateがサポートする言語数は、使用する翻訳サービスによって異なります：

#### 主要な翻訳サービスの言語サポート数

| サービス名 | サービスコード | サポート言語数 | 特徴 |
|-----------|--------------|--------------|------|
| **Google Translate** | `google` | **100以上の言語** | デフォルトサービス、無料、最も多くの言語をサポート |
| **DeepL** | `deepl` | **31言語** | 高品質な翻訳、特にヨーロッパ言語に強い |
| **Argos Translate** | `argos` | **100以上の言語** | オープンソース、ローカル実行可能 |
| **Bing Translator** | `bing` | **60以上の言語** | マイクロソフト提供 |
| **OpenAI (GPT)** | `openai` | **多数の言語** | 高品質、APIキー必要 |
| **Azure OpenAI** | `azure-openai` | **多数の言語** | エンタープライズ対応 |
| **Ollama** | `ollama` | **モデル依存** | ローカル実行、カスタムモデル対応 |
| **その他** | 各種 | **サービスにより異なる** | 環境変数の設定が必要 |

**推奨**: 最も多くの言語をサポートするのは **Google Translate** (`google`) で、100以上の言語に対応しています。デフォルトで使用されるため、追加設定は不要です。

### 主要な言語コード例

```swift
// よく使われる言語コードの例
let commonLanguages: [String: String] = [
    // アジア言語
    "en": "English (英語)",
    "zh": "Simplified Chinese (簡体字中国語)",
    "zh-TW": "Traditional Chinese (繁体字中国語)",
    "ja": "Japanese (日本語)",
    "ko": "Korean (韓国語)",
    "th": "Thai (タイ語)",
    "vi": "Vietnamese (ベトナム語)",
    "id": "Indonesian (インドネシア語)",
    "hi": "Hindi (ヒンディー語)",
    "ar": "Arabic (アラビア語)",
    
    // ヨーロッパ言語
    "fr": "French (フランス語)",
    "de": "German (ドイツ語)",
    "es": "Spanish (スペイン語)",
    "it": "Italian (イタリア語)",
    "pt": "Portuguese (ポルトガル語)",
    "ru": "Russian (ロシア語)",
    "nl": "Dutch (オランダ語)",
    "pl": "Polish (ポーランド語)",
    "tr": "Turkish (トルコ語)",
    "sv": "Swedish (スウェーデン語)",
    "da": "Danish (デンマーク語)",
    "no": "Norwegian (ノルウェー語)",
    "fi": "Finnish (フィンランド語)",
    "cs": "Czech (チェコ語)",
    "hu": "Hungarian (ハンガリー語)",
    "ro": "Romanian (ルーマニア語)",
    "el": "Greek (ギリシャ語)",
    "he": "Hebrew (ヘブライ語)",
    
    // その他
    "af": "Afrikaans",
    "sw": "Swahili",
    "zu": "Zulu",
    // ... 100以上の言語がサポートされています
]
```

### 言語コードの確認方法

完全な言語コードリストは、各サービスの公式ドキュメントを参照してください：

- **Google Translate**: [Google Languages Codes](https://developers.google.com/admin-sdk/directory/v1/languages)
- **DeepL**: [DeepL Supported Languages](https://developers.deepl.com/docs/resources/supported-languages)
- **Bing**: [Bing Translator Languages](https://learn.microsoft.com/azure/ai-services/translator/language-support)

### 使用例

```swift
// 例1: 英語から中国語（簡体字）への翻訳（Google Translate - 100以上の言語をサポート）
let options1 = TranslateOptions(
    langIn: "en",
    langOut: "zh",
    service: "google",  // デフォルト、追加設定不要
    thread: 4
)

// 例2: 日本語から英語への翻訳（DeepL - 31言語、高品質）
let options2 = TranslateOptions(
    langIn: "ja",
    langOut: "en",
    service: "deepl",  // APIキーが必要な場合あり
    thread: 4
)

// 例3: 英語からフランス語への翻訳
let options3 = TranslateOptions(
    langIn: "en",
    langOut: "fr",
    service: "google",
    thread: 4
)
```

## 注意事項

### 1. メモリ管理

大きなPDFファイルを処理する場合、メモリ使用量に注意してください。

```swift
// 大きなファイルの場合は、ストリーミング処理を検討
// または、ファイルサイズ制限を設定

func checkFileSize(_ data: Data) -> Bool {
    let maxSize = 50 * 1024 * 1024 // 50MB
    return data.count <= maxSize
}
```

### 2. ネットワーク接続

ネットワーク接続が不安定な場合の対応：

```swift
// URLSessionの設定
let config = URLSessionConfiguration.default
config.timeoutIntervalForRequest = 30
config.timeoutIntervalForResource = 300
config.waitsForConnectivity = true

let session = URLSession(configuration: config)
let apiClient = PDFTranslateAPIClient(
    baseURL: "https://pdfmathtranslate-production-cf37.up.railway.app",
    session: session
)
```

### 3. バックグラウンド処理

バックグラウンドでも動作させる場合：

```swift
// AppDelegateまたはSceneDelegateで
let config = URLSessionConfiguration.background(withIdentifier: "com.yourapp.pdftranslate")
let session = URLSession(configuration: config)
```

### 4. Info.plist設定

HTTPS以外のURLを使用する場合（通常は不要）：

```xml
<key>NSAppTransportSecurity</key>
<dict>
    <key>NSAllowsArbitraryLoads</key>
    <false/>
    <key>NSExceptionDomains</key>
    <dict>
        <key>pdfmathtranslate-production-cf37.up.railway.app</key>
        <dict>
            <key>NSExceptionAllowsInsecureHTTPLoads</key>
            <false/>
            <key>NSIncludesSubdomains</key>
            <true/>
        </dict>
    </dict>
</dict>
```

### 5. 翻訳オプションのパラメータ

#### 翻訳サービスとサポート言語数

PDFMathTranslateは複数の翻訳サービスをサポートしており、各サービスがサポートする言語数は異なります：

| サービス | サービスコード | サポート言語数 | 備考 |
|---------|--------------|--------------|------|
| **Google Translate** | `google` | **100以上の言語** | デフォルト、無料、最も多くの言語をサポート |
| **DeepL** | `deepl` | **31言語** | 高品質な翻訳、APIキーが必要な場合あり |
| **Argos Translate** | `argos` | **100以上の言語** | オープンソース、翻訳品質は中程度 |
| **Bing** | `bing` | 多数 | 無料 |
| **OpenAI** | `openai` | 多数 | APIキーが必要、高品質 |
| **Azure OpenAI** | `azure-openai` | 多数 | APIキーが必要 |
| **Ollama** | `ollama` | モデル依存 | ローカル実行可能 |
| **その他** | 各種 | サービスにより異なる | 環境変数の設定が必要 |

#### 主要な言語コード

```swift
// 主要な言語コードの例
let languageCodes: [String: String] = [
    "en": "English (英語)",
    "ja": "Japanese (日本語)",
    "zh": "Simplified Chinese (簡体字中国語)",
    "zh-TW": "Traditional Chinese (繁体字中国語)",
    "ko": "Korean (韓国語)",
    "fr": "French (フランス語)",
    "de": "German (ドイツ語)",
    "es": "Spanish (スペイン語)",
    "it": "Italian (イタリア語)",
    "ru": "Russian (ロシア語)",
    "pt": "Portuguese (ポルトガル語)",
    "ar": "Arabic (アラビア語)",
    "hi": "Hindi (ヒンディー語)",
    "nl": "Dutch (オランダ語)",
    "pl": "Polish (ポーランド語)",
    "tr": "Turkish (トルコ語)",
    "th": "Thai (タイ語)",
    "vi": "Vietnamese (ベトナム語)",
    "id": "Indonesian (インドネシア語)",
    // ... その他100以上の言語がサポートされています
]
```

#### 言語コードの確認方法

完全な言語コードリストは、各サービスのドキュメントを参照してください：

- **Google Translate**: [Google Languages Codes](https://developers.google.com/admin-sdk/directory/v1/languages)
- **DeepL**: [DeepL Supported Languages](https://developers.deepl.com/docs/resources/supported-languages)

#### 使用例

```swift
// Google Translateを使用（100以上の言語をサポート）
let options = TranslateOptions(
    langIn: "en",
    langOut: "zh",
    service: "google",  // デフォルト
    thread: 4
)

// DeepLを使用（31言語、高品質）
let deeplOptions = TranslateOptions(
    langIn: "en",
    langOut: "ja",
    service: "deepl",  // APIキーが必要な場合あり
    thread: 4
)
```

---

## 完全な実装例

以下は、全ての機能を含む完全な実装例です。

```swift
import Foundation

class PDFTranslateService {
    private let apiClient: PDFTranslateAPIClient
    
    init(baseURL: String) {
        self.apiClient = PDFTranslateAPIClient(baseURL: baseURL)
    }
    
    // 完全な翻訳フロー
    func translatePDF(
        pdfData: Data,
        options: TranslateOptions,
        progressCallback: @escaping (Int, Int) -> Void,
        completion: @escaping (Result<Data, Error>) -> Void
    ) {
        Task {
            do {
                // 1. ヘルスチェック（オプション）
                let isHealthy = try await apiClient.healthCheck()
                guard isHealthy else {
                    await MainActor.run {
                        completion(.failure(APIError.serverError("Server is not available")))
                    }
                    return
                }
                
                // 2. タスクを作成
                let taskId = try await apiClient.createTranslateTask(
                    pdfData: pdfData,
                    options: options
                )
                
                // 3. 状態をポーリング
                while true {
                    let status = try await apiClient.checkTaskStatus(taskId: taskId)
                    
                    if status.state == "PROGRESS", let info = status.info {
                        await MainActor.run {
                            progressCallback(info.n, info.total)
                        }
                    } else if status.state == "SUCCESS" {
                        // 4. 完了したらPDFをダウンロード
                        let pdfData = try await apiClient.downloadTranslatedPDF(
                            taskId: taskId,
                            format: .dual
                        )
                        await MainActor.run {
                            completion(.success(pdfData))
                        }
                        break
                    } else if status.state == "FAILURE" {
                        await MainActor.run {
                            completion(.failure(APIError.taskFailed))
                        }
                        break
                    }
                    
                    // 2秒待機
                    try await Task.sleep(nanoseconds: 2_000_000_000)
                }
            } catch {
                await MainActor.run {
                    completion(.failure(error))
                }
            }
        }
    }
}
```

---

## トラブルシューティング

### よくある問題

1. **ネットワークエラー**
   - インターネット接続を確認
   - API URLが正しいか確認

2. **タイムアウトエラー**
   - タイムアウト時間を延長
   - ファイルサイズが大きすぎないか確認

3. **エンコーディングエラー**
   - PDFデータが正しく読み込まれているか確認
   - JSONエンコードが正しく行われているか確認

4. **タスクが完了しない（PENDINGのまま）**
   - **最も一般的な原因**: Celeryワーカーが起動していない
   - **解決方法**:
     - RailwayでCeleryワーカーを別のサービスとして追加
     - ワーカーサービスのStart Command: `pdf2zh --celery worker --loglevel=info`
     - ワーカーサービスが起動しているか確認
     - ワーカーサービスのログを確認
   - 詳細は[Railwayデプロイガイド](./RAILWAY_DEPLOY.md)を参照

---

## Railwayでのデプロイ

RailwayでAPIをデプロイする場合、**必ずCeleryワーカーを別のサービスとして追加**する必要があります。

詳細な手順については、[Railwayデプロイガイド](./RAILWAY_DEPLOY.md)を参照してください。

**重要**: APIサーバーだけでは翻訳タスクは処理されません。Celeryワーカーサービスも必ず作成してください。

---

## サンプルプロジェクト

完全なサンプルプロジェクトは、GitHubリポジトリのサンプルディレクトリを参照してください。

---

## サポート

問題が発生した場合：
1. APIサーバーのログを確認
2. Workerサービスのログを確認
3. ヘルスチェックエンドポイントで状態を確認
4. Railwayを使用している場合、[Railwayデプロイガイド](./RAILWAY_DEPLOY.md)のトラブルシューティングセクションを参照

---

**API Base URL:** `https://pdfmathtranslate-production-cf37.up.railway.app`

**最終更新:** 2025-11-28

