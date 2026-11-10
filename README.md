# AnalysisTemplate — 2026年12月 PF-AR ビームテスト用 解析テンプレート

[English version](README.en.md)

PF-AR の MALTA2 テレスコープのデータを Corryvreckan で解析するためのテンプレートです。
ビームテストの前に config と geometry を用意しておき、当日は **面の z 位置を書き換えるだけ** で
アライメントから解析・オンラインモニターまで流せるようにしてあります。

| 用途 | ディレクトリ | 用意してある setup |
|---|---|---|
| テレスコープ (RP 6枚 + DUT 1枚、DUT = MALTA2) | `Telescope/` | `dec2026_C1p5` (全部の間隔 1.5cm) |
| 物質量イメージング (RP 6枚、サンプルは z = 0) | `Imaging/` | `dec2026_EDA` (EDA ボードの実測位置) |

## 1. 考え方: setup

「setup」は 1つの配置のことで、`geometry/<setup>/init.conf` に各面の z 位置を書いたものです。
解析の各ステップは、前のステップが書いた geometry を読んで、次の geometry を書きます。
Telescope では、アライメントに使った run ごとにディレクトリ `geometry/<setup>/run<A>/` を分けるので、
別の run でアラインし直しても前のアライメントは残ります (A = アライメントに使った run)。

```
Telescope:  geometry/<setup>/init.conf ─(コピー)→ run<A>/init.conf → masked → prealigned → aligned → aligned_dut .conf
Imaging:    geometry/<setup>/init.conf → masked → prealigned → aligned .conf
結果:       Telescope は output/<setup>/run<N>/<step>/、Imaging は output/<setup>/<step>/
            (corry の root、ログ、まとめの図。N はそのステップが読んだ run)
```

- `init.conf` に書くのは **z だけ** です (1mm くらいの精度で十分)。x/y のずれと回転は、
  Prealignment / Alignment (Millepede) / AlignmentDUT が求めます。
- config (`config/*.conf`) はすべての setup で共通です。setup ごとに変えるのは geometry だけです。
- 配置ごとに別の setup にしておけば、結果が混ざりません。

## 2. ディレクトリ構成

```
AnalysisTemplate/
├── README.md / README.en.md
├── paths.example.json            マシンごとのパスの雛形 (→ paths.json にコピーして編集。git には入れない)
├── common/                       paths.sh (paths.json の読み込み), PlotStyle.h / MacroUtils.h (マクロ共通)
├── Telescope/
│   ├── config/                   mask, prealign, align, align_dut, analysis, analysis_upstream3, online
│   ├── geometry/
│   │   ├── template/init.conf    setup の雛形 (z の行に "EDIT" の印)
│   │   ├── dec2026_C1p5/         RP–RP、RP–DUT の間隔がすべて 1.5cm
│   │   │   ├── init.conf         この setup の z 位置 (手で書く)
│   │       └── run<A>/           run A でのアライメント (init のコピー、masked … aligned_dut)
│   ├── scripts/
│   │   ├── run_chain.sh          corry: mask → prealign → align → align_dut → analysis (→ upstream3)
│   │   ├── run_online.sh         オンラインモニター
│   │   └── run_ABscan.sh, plot_ABscan_sigma.sh   (シミュレーション専用の距離スキャン)
│   ├── macros/                   plot_<step>.C (各ステップの図を作る ROOT マクロ)
│   ├── data/                     run_<NNNNNN>_<0..6>.root を置く場所 (既定)
│   └── output/<setup>/run<N>/<step>/
└── Imaging/
    ├── config/                   mask, prealign, align, imaging, online
    ├── geometry/
    │   ├── template/init.conf
    │   └── dec2026_EDA/          EDA ボードの実測位置 (RD53B の面 = サンプル = z 0)
    ├── scripts/
    │   ├── run_imaging.sh        mask → prealign → align (サンプルなしの run) → imaging → plot
    │   ├── run_online.sh         オンラインモニター
    │   └── calibrate_xx0.sh      Al 板による x/X0 への較正
    ├── macros/                   plot_imaging.C (画像の作図), calibrate_xx0.C
    ├── data/                     run_<NNNNNN>_<0..5>.root を置く場所 (既定)
    └── output/<setup>/
```

## 3. 用意してある配置

**Telescope `dec2026_C1p5`** (ビームは +z 方向、MALTA_3 が DUT):

```
MALTA_0 –1.5– MALTA_1 –1.5– MALTA_2 –1.5– [MALTA_3 = DUT] –1.5– MALTA_4 –1.5– MALTA_5 –1.5– MALTA_6   [cm]
  −45           −30           −15              0              +15          +30          +45     [mm]
```

**Imaging `dec2026_EDA`** (RD53B の面を z = 0 にして、そこにサンプルを置く。1番の面からビームが入る):

```
MALTA_0 –110– MALTA_1 –110– MALTA_2 –61.65– [sample] –48.35– MALTA_4 –110– MALTA_5 –110– MALTA_6   [mm]
 −281.65      −171.65       −61.65           0          +48.35        +158.35       +268.35  [mm]
```

## 4. 前提

- 必要なのは **bash, corry, ROOT だけ** です (Python・venv は不要)。corry を実行するのは bash スクリプト、
  図を作るのは ROOT マクロ (`Telescope/macros/*.C`, `Imaging/macros/*.C`) です。
- **パスは `paths.json` に書く** (マシンごとに 1つ、git には入れない)。clone したらまず:
  ```bash
  cp paths.example.json paths.json   # 中身をそのマシンに合わせて編集
  ```
  | キー | 意味 |
  |---|---|
  | `env_setup` | 最初に source するスクリプト (例: `thisroot.sh` や LCG の `setup.sh`)。不要なら `""` |
  | `corry_bin` | corry の実行ファイル (`"corry"` なら PATH から探す) |
  | `root_bin` | root の実行ファイル (`"root"` なら PATH から探す) |
  | `telescope_data_dir` | Telescope の `--data-dir` の既定値 |
  | `imaging_data_dir` | Imaging の `--data-dir` の既定値 |
  | `plot_dir` | Imaging / ABscan の図の置き場 (`<plot_dir>/{real,simulation}_analyze/<分類>/`)。`""` ならリポジトリ内の `output/` |
  | `sim_config_dir` | シミュレーションの generator のある場所 (ABscan 専用。ビームテストでは `""` でよい) |

  相対パスはリポジトリの一番上から見たものです。環境変数 (`CORRY_BIN`, `ROOT_BIN`, `PLOT_DIR` など、
  キーを大文字にしたもの) を付けると、その場だけ上書きできます。
- データ: MaltaDAQ の `run_<6桁の run 番号>_<面の番号>.root` (EventLoaderMALTA の形式)
  - Telescope: 面の番号 0..6 = MALTA_0..MALTA_6
  - Imaging: 面の番号 0..5 = MALTA_0, 1, 2, 4, 5, 6 (3 = DUT の位置は空き)
- config はすべて **実データ (`real_data = true`) が既定** です。Allpix の `Malta2TreeWriter` で作った
  シミュレーションのデータには、必ず `--sim-data` を付けてください。

## 5. ビームテスト当日の流れ

1. **z 位置を測って setup を作る** (用意した配置どおりなら不要)。template をコピーして、
   `# <-- EDIT` の付いた `position` の行の z (3つ目の値) だけを、上流の面から順に書き換えます:
   ```bash
   cp -r Telescope/geometry/template Telescope/geometry/dec2026_run1
   cp -r Imaging/geometry/template   Imaging/geometry/dec2026_img1
   # それぞれの init.conf を開いて z を直す (例: position = 0um, 0um, -45mm)
   ```
   z の単位は付けて書きます (mm でも cm でもよい)。役割 (`role`) の行は変えないでください。
2. **最初の run の間にオンラインモニターを起動する**。まだアライメントがないので init.conf を使い、
   ヒットマップと相関を見ます (残差と効率はまだ意味がない)。
   ```bash
   Telescope/scripts/run_online.sh --setup dec2026_C1p5 --run 120 --data-dir /path/to/maltadaq/data
   ```
3. **統計のたまった run でアライメントする** (prealign は 20万イベント、align / align_dut は 1万イベントを使う):
   ```bash
   Telescope/scripts/run_chain.sh --setup dec2026_C1p5 --run 120 --data-dir /path/to/data
   ```
4. **オンラインモニターを起動し直す**。今度は一番新しいアライメント (`run120/aligned_dut.conf`) が自動で選ばれ、
   DUT の残差と効率が見える。
5. **同じ配置の他の run は、アライメントを使い回して解析だけする**:
   ```bash
   Telescope/scripts/run_chain.sh --setup dec2026_C1p5 --align-run 120 --run 121 --steps "analysis upstream3"
   ```
   アライメントは `geometry/dec2026_C1p5/run120/` に残るので、後で別の run (例: 130) でアラインし直しても、
   `--align-run 120` で前のアライメントをいつでも使えます。配置を動かしたら、新しい setup を作ってアライメントからやり直します。

## 6. テレスコープの解析 (`Telescope/`)

```bash
cd Telescope/scripts
./run_chain.sh --setup dec2026_C1p5 --run 120 [--data-dir DIR] [--events N] [--sim-data]
./run_chain.sh --setup dec2026_C1p5 --run 120 --steps "mask prealign align align_dut analysis upstream3"
```

| ステップ | config | 内容 | 書く geometry |
|---|---|---|---|
| `mask` | `mask.conf` | ノイズの多いピクセルのマスク | `masked.conf` |
| `prealign` | `prealign.conf` | 相関から x/y のずれを粗く決める (DUT は固定) | `prealigned.conf` |
| `align` | `align.conf` | Millepede で RP 6枚をアライン (DUT は除く) | `aligned.conf` |
| `align_dut` | `align_dut.conf` | RP のトラックで DUT だけを合わせる | `aligned_dut.conf` |
| `analysis` | `analysis.conf` | RP 6枚の tracking、DUT の効率・残差 | — |
| `upstream3` | `analysis_upstream3.conf` | 上流 RP 3枚だけの tracking (DUT へ外挿) | — |

- 結果: `output/<setup>/run<N>/<step>/` に `*.root`、`run<N>_corry.log`、`run<N>_summary.png/pdf`
  (analysis は `run<N>_residuals.png` も)。N はそのステップが読んだ run なので、
  `--align-run 120 --run 121` ならアライメントは `run120/`、解析は `run121/` に入ります。
- 1ステップだけ: `--steps prealign`。corry をやり直さずに図だけ作り直す: `--plot-only`。
  マクロを直接呼ぶこともできます: `root -l -b -q 'macros/plot_prealign.C("<root file>","<出力先>","120","MALTA_0,...,MALTA_6","MALTA_3")'`
- `--dut MALTA_x` で DUT にする面を変えられます (Telescope/README.md 参照)。

## 7. イメージングの解析 (`Imaging/`)

サンプルを置いていない run でアラインし、サンプルを置いた run をイメージングします
(まっすぐな 6面のトラックで正しくアラインできるのは、z = 0 に何もないときだけです)。

```bash
cd Imaging/scripts
./run_imaging.sh --setup dec2026_EDA --data-dir DIR --align-run 11 --image-run "12 13"
./run_imaging.sh --setup dec2026_EDA --data-dir DIR --image-run 14 --steps "imaging plot"   # アライメント済みなら
```

- 画像は、セルごとのキンク角の幅 (中央 90% の AAD、x と y をまとめたもの) です。x/X0 ではありません。
  x/X0 にするには、同じ配置で厚さのわかった Al 板の run を撮り、`scripts/calibrate_xx0.sh` で較正します
  (Imaging/README.md 参照)。
- 図: `<plot_dir>/real_analyze/material_imaging/<setup>/MLCC_run<N>_{image,tracks,xprofile,kink}.png`
  (`--sim-data` のときは `simulation_analyze/`。`plot_dir` が空なら `Imaging/output/<setup>/plots/`)。
- **統計の目安**: 1セルに 20本 (`min_cell_content`) ないと値が出ません。EDA 配置のシミュレーションでは、
  100µm セルは約 160万トラックで全面が埋まり、10万トラックでは MLCC の上がほぼ空白でした。
  10万トラックなら 200µm セルにします
  (`config/imaging.conf` の `cell_size`、または `-o AnalysisMaterialBudget.cell_size=200um,200um`)。
- 画像の範囲は `config/imaging.conf` の `image_size = 18mm 9mm` (MALTA2 1枚分) です。

## 8. オンラインモニター

データを取っている最中の run ファイルを読んで、ヒットマップ・相関・トラック・残差・効率などを
リアルタイムに表示します。設定は Telescope / Imaging それぞれの `config/online.conf` です。

### 8.1 起動と終了

```bash
Telescope/scripts/run_online.sh --setup dec2026_C1p5 --run 121 --data-dir DIR
Imaging/scripts/run_online.sh   --setup dec2026_EDA  --run 12  --data-dir DIR
```

- MaltaDAQ が書いている途中のファイルを読むので、run の開始と同時に起動できます。geometry は書き換えません。
- **画面 (X11) が必要**です。ssh なら `ssh -X` / `ssh -Y` で入ってください。
- geometry の選び方:
  - Telescope: `--align-run A` があればそのアライメント (`run<A>/` の aligned_dut > aligned > prealigned > init)、
    なければ一番新しく終わったアライメント (`run*/aligned_dut.conf` で最新のもの)、それもなければ setup の init.conf。
    どれを使ったかは、起動時に `geometry: …` と表示されます。
  - Imaging: setup にある aligned > prealigned > masked > init の順。
  - `--geometry FILE` で直接指定もできます。アライメント前 (init.conf) は、ヒットマップと相関だけを見てください。
- 起動し直すとヒストグラムは 0 から始まります。アライメントが済んだら、起動し直すと新しい geometry になります。
- 終了はウィンドウを閉じるか、ターミナルで Ctrl-C。
- 1分ごとのスナップショット (PNG): Telescope は `output/<setup>/run<N>/online/snapshots/`、
  Imaging は `output/<setup>/online/snapshots/`。全ヒストグラムは終了時に同じ場所の `online.root` に書かれます。
- `--sim-data` でシミュレーションのデータも表示できます (練習用)。

### 8.2 画面の見方

左のボタンでキャンバスを切り替えます。キー操作:

| キー | 動作 |
|---|---|
| `Space` | 一時停止 / 再開 |
| `F` | 今のキャンバスを全画面に |
| `S` | 今のキャンバスを PNG で保存 |
| `1`〜`9` | Overview, Tracking Performance, Residuals X, Residuals Y, Res Trends, Timeline, Corr Trends, Hitmaps, Event Times |

キャンバスの一覧と、中身を config で変えられるかどうか (変えられるものは「設定のキー」の名前で上書きします):

| キャンバス | 既定の中身 | 設定のキー |
|---|---|---|
| Overview | χ²/ndf、reference 面のヒットマップと残差 | `overview` |
| Tracking Performance | χ²、角度 X/Y、tracks/event、clusters/track | `tracking` |
| Residuals X / Y | 面ごとの残差 (DUT を除く) | `residuals` / `residuals_y` |
| Hitmaps | 面ごとのヒットマップ | `hitmaps` |
| Event Times | 面ごとのイベント時刻 | `event_times` |
| Cluster Size | 面ごとのクラスタサイズ | `cluster_size` |
| 1D X / 1D Y | 面ごとの相関 (1次元) | `correlation_x` / `correlation_y` |
| 2D X / 2D Y | 面ごとの相関 (2次元) | `correlation_x2d` / `correlation_y2d` |
| DUTs (DUT ごとに1枚) | DUT のヒットマップ、残差 X/Y、効率マップ | `dut_plots` |
| Res Trends, Timeline, Corr Trends, L1idC | 残差・クラスタ数・相関の時間変化、DAQ の健全性 | 変更不可 |

各プロットの見どころ (どこを見ればよいか) は、corry の
`src/modules/OnlineMonitor/PLOT_GUIDE.md` に詳しく書いてあります。

### 8.3 自分の見たいプロットを置く

**新しいキャンバスは足せません。** 上の表の「設定のキー」があるキャンバスの中身を、
`config/online.conf` の `[OnlineMonitor]` に書いて **置き換え** ます。書いたキャンバスは、既定の中身が全部消えて
書いたものだけになります (足すのではなく置き換え。残したい既定のプロットも一緒に書く)。

書き方は、`[ヒストグラムのパス, 描き方]` を並べた行列です:

```toml
[OnlineMonitor]
overview = [["Tracking4D/trackChi2ndof"], ["Correlations/%REFERENCE%/hitmap", "colz"], ["Tracking4D/tracksPerEvent", "log"]]
```

- **1行で書く**: corry の config は行の継続ができません。どんなに長くても1行です。
- **パス** = `モジュール名/検出器名/…/ヒストグラム名` (結果の ROOT ファイルの中と同じ。調べ方は 8.4)。
- **置き換えの記号**:
  - `%REFERENCE%` → reference 面 (MALTA_0) の1枚
  - `%DETECTOR%` → すべての面について1枚ずつ (Residuals X/Y では DUT を除く)
  - `%DUT%` → DUT について1枚 (`dut_plots` では、そのキャンバスの DUT)
- **描き方** (2つ目、省略可): 2次元なら `"colz"`。`"log"` を含めると y 軸が log になる (`"colz log"` のように併用も可)。
  それ以外は ROOT の Draw オプションとして渡されます (`"hist"` など)。
- 描けるのは TH1 / TH2 / TProfile だけです。`TEfficiency` (例: `AnalysisEfficiency/MALTA_3/chipEfficiencyMap_trackPos`)
  は描けないので、`_TProfile` の付いた版を使います。
- **パスを間違えると、何も言わずに表示されません** (エラーにならない)。出ないときはまずパスを確認してください。
- 表示できるのは、**`online.conf` の中で動いているモジュールのヒストグラムだけ**です。
  見たいヒストグラムを作るモジュールがなければ、そのモジュールのセクションを `online.conf` に足します。

**例1: DUT のキャンバスにクラスタサイズを足す** (Telescope)。クラスタサイズは Clustering4D が作るので、そのまま書けます:

```toml
dut_plots = [["Correlations/%DUT%/hitmap", "colz"], ["OnlineMonitor/dut_residual_x_%DUT%"], ["OnlineMonitor/dut_residual_y_%DUT%"], ["AnalysisEfficiency/%DUT%/chipEfficiencyMap_trackPos_TProfile", "colz"], ["Clustering4D/%DUT%/clusterSize", "log"]]
```

**例2: DUT の in-pixel 効率を見る** (Telescope)。AnalysisEfficiency はもう `online.conf` で動いているので、パスを足すだけ:

```toml
dut_plots = [["AnalysisEfficiency/%DUT%/chipEfficiencyMap_trackPos_TProfile", "colz"], ["AnalysisEfficiency/%DUT%/pixelEfficiencyMap_trackPos_TProfile", "colz"], ["OnlineMonitor/dut_residual_x_%DUT%"], ["OnlineMonitor/dut_residual_y_%DUT%"]]
```

**例3: まだ動いていないモジュールのヒストグラムを出す**。例えば DUT の関連付けたクラスタのサイズ
(`AnalysisDUT/%DUT%/clusterSizeAssociated`) は AnalysisDUT が作るので、先に `online.conf` に
`[AnalysisDUT]` のセクションを足します。ただし AnalysisDUT は約 4GB のヒストグラムを確保するので、
オンラインでは重くなります (そのため既定では入れていない)。足すモジュールは、軽いものにしてください。

**例4: Imaging の Overview を変える**。Imaging の `online.conf` は、トラッカーが `TrackingMultiplet`
なので、Overview / Tracking / Residuals をあらかじめ TrackingMultiplet と AnalysisMaterialBudget の
ヒストグラムで書き換えてあります。例えば y 方向のキンク角も見たいなら:

```toml
overview = [["AnalysisMaterialBudget/MBIpreview", "colz"], ["TrackingMultiplet/multipletKinkAtScattererX"], ["TrackingMultiplet/multipletKinkAtScattererY"], ["TrackingMultiplet/matchingDistanceAtScattererX"]]
```

### 8.4 ヒストグラムのパスの調べ方

一度オンラインモニターかオフライン解析を流して、できた ROOT ファイルの中を見ます。

```bash
rootls -r Telescope/output/dec2026_C1p5/run121/online/online.root | less          # 全部 (長い)
rootls Telescope/output/dec2026_C1p5/run121/analysis/analysis.root:AnalysisEfficiency/MALTA_3   # 1つのディレクトリ
```

- ROOT のブラウザ (`root -l online.root` → `new TBrowser`) でも同じです。
- 面の名前のところを `%DETECTOR%` / `%DUT%` / `%REFERENCE%` に置き換えて書けば、全部の面に展開されます。
- `OnlineMonitor/…` のヒストグラム (例: `dut_residual_x_MALTA_3`) は、オンラインモニター自身が作るものです。

### 8.5 そのほかの設定 (`[OnlineMonitor]`)

| キー | 今の値 | 意味 |
|---|---|---|
| `update` | 200 | 何イベントごとに画面を更新するか (最大でも 1秒に1回、また 5秒に1回は必ず更新) |
| `target_events` | 500000 (Telescope) / 2000000 (Imaging) | 進捗バーの目標。全 RP にヒットがあったイベントだけを数える |
| `auto_save_interval` | 60 | スナップショットの間隔 [秒] (0 で保存しない) |
| `auto_save_dir` | `"snapshots/"` | 保存先 (`output_directory` からの相対パス。`run_online.sh` が作る) |
| `canvas_title` | — | ウィンドウのタイトル (`run_online.sh` が setup 名と run 番号を入れる) |
| `display_max_bins_1d` / `_2d` | 2000 / 300 | これより細かいヒストグラムは、表示だけ粗くする (保存される中身は変わらない) |

Tracking4D / AnalysisEfficiency などのカットは、オフラインの `analysis.conf` と揃えてあります。
オンラインの Tracking4D は `min_hits_on_track = 6` なので、RP が1枚止まるとトラックがなくなります
(Timeline と L1idC のキャンバスで気づけます)。

## 9. シミュレーションで試す

用意した配置と同じジオメトリのシミュレーションがあるので、当日の前に手順を確認できます。

```bash
# Telescope: ABscan の run 15 (A = B = C = 1.5cm) は dec2026_C1p5 と同じ配置
Telescope/scripts/run_chain.sh --setup dec2026_C1p5 --run 15 --sim-data --events 30000 \
    --steps "mask prealign align align_dut analysis upstream3"
#   → DUT 効率 99.99%、残差 σ ≈ 10.8 µm (6枚) / 17.9 µm (上流3枚)

# Imaging: MLCC_imaging_EDA の run 1 (サンプルなし) と run 3 (MLCC + PCB 0.22mm)
Imaging/scripts/run_imaging.sh --setup dec2026_EDA --sim-data \
    --data-dir <sim>/output/MLCC_imaging_EDA --align-run 1 --image-run 3
```

試したあとは、Telescope は `geometry/<setup>/run*/`、Imaging は `geometry/<setup>/` の init.conf 以外
(masked, prealigned, aligned) と、`output/<setup>/` を消してから当日を迎えてください。シミュレーションでアラインした geometry が残っていると、
オンラインモニターがそれを使ってしまいます。

## 10. 注意点

- **シミュレーションには `--sim-data`**: 付けないと、実機用のグループアドレスの補正がかかって、ヒットの位置がずれます。
- **`mask_dead_pixels = false`** (Telescope / Imaging とも): ビームが当たらないピクセルが「dead」と判定されて
  マスクされ、AnalysisEfficiency がマスクの隣を通るトラックをほぼすべて捨ててしまうためです
  (シミュレーションで 30704 本中 85 本しか残らなかった)。ノイズの多いピクセルだけをマスクします。
- **corry が終了時にたまにクラッシュする** (`double free or corruption`): 結果を書き終えた後なので、
  Telescope のスクリプトは警告を出して続けます。Imaging でこれが出たら、同じコマンドをもう一度流してください。
- **アライメントの geometry**: Telescope は run ごとに `geometry/<setup>/run<A>/` に分かれるので、別の run でアラインしても
  前のものは残ります。**同じ run** でアラインし直したときだけ、その `run<A>/` が上書きされます。
  Imaging はまだ setup ごとに1つなので、アラインし直すと上書きされます (残したいときは setup を分ける)。
- `geometry/<setup>/init.conf` を書き換えても、すでにある `run<A>/init.conf` (そのアライメントに使ったもののコピー) は変わりません。
- 新しい解析 config を足すときは `config/` に置き、`Telescope/scripts/run_chain.sh --setup <setup> --run N --steps analysis --analysis-config config/<新しい>.conf`
  で流せます (出力は `output/<setup>/run<N>/<config の output_directory の名前>/`)。
- **output のディレクトリを動かさない**: mask の結果 (`mask_file`) は geometry の中に絶対パスで書かれます。
  `output/<setup>/run<N>/mask/` を動かしたり消したりすると、その setup の geometry が読めなくなります
  (動かしたときは、`geometry/<setup>/run<A>/*.conf` の `mask_file` のパスも直す)。
  同じ理由で、`geometry/<setup>/run<A>/` を別のマシンに持っていかないでください (そのマシンでアラインし直す)。
