# Packed flip uniformの単独Metal診断

`scripts/page-recovery/metal_flip_probe.mm`は、Chromiumを起動せず、架空入力だけでMetalのpacked signed-normalized decodeと頂点Y補正を比較する診断です。app、profile、Keychain、署名を操作しません。実機での実行にはオーナー承認が必要です。結果は非公開領域に保存し、WebGLやKOOVの受入には読み替えません。

調査対象はANGLE `8efd15f71c27cd0bc2a9cf0074d77e899ca9c448`です。[ContextMtl.mm](https://github.com/google/angle/blob/8efd15f71c27cd0bc2a9cf0074d77e899ca9c448/src/libANGLE/renderer/metal/ContextMtl.mm)が`flipXY`をpackし、[DriverUniform.cpp](https://github.com/google/angle/blob/8efd15f71c27cd0bc2a9cf0074d77e899ca9c448/src/compiler/translator/tree_util/DriverUniform.cpp)がunpackした成分を選び、[TranslatorMSL.cpp](https://github.com/google/angle/blob/8efd15f71c27cd0bc2a9cf0074d77e899ca9c448/src/compiler/translator/msl/TranslatorMSL.cpp)がvertex positionのY補正を追加します。[EmitMetal.cpp](https://github.com/google/angle/blob/8efd15f71c27cd0bc2a9cf0074d77e899ca9c448/src/compiler/translator/msl/EmitMetal.cpp)ではbuiltinの`metal::unpack_snorm4x8_to_float`へ変換されます。この経路は調査仮説であり、原因を確定したものではありません。

診断はfast math無効／有効の両方で、runtime既定のMSL versionを使います。7種類の架空packed値についてbuiltinと明示的な符号拡張・除算をCPU参照値と比べます。さらに32×32のoffscreen textureへ、補正なし／builtin補正／scalar補正で三角形を描き、正負のflipについて中心pixelと緑pixel数を記録します。uniformのsizeとflip offsetはC++のstatic assertionで固定しています。

コンパイルにはFoundationとMetal framework、ARC、C++17を使います。コンパイルだけではGPU診断は動きません。実行形式は`metal-flip-probe --run --out NEW_PRIVATE_JSON`で、既存出力は上書きせず、新規JSONをowner-onlyで作ります。新しいGPU processとMetal compiler/cacheの使用は伴います。ウィンドウ・prompt操作はありません。各command bufferの待機上限は10秒です。

`completed`は診断処理の終了だけを示します。親はdecodeの有限値・CPU参照との一致、各render結果、両fast math設定をレビューします。不一致、compile失敗、command失敗、timeoutはいずれも受入ではありません。単独診断が通っても、ANGLEが実際に生成したMSL・uniform値・binding・viewportの照合が残ります。実機結果・画像・識別情報はGitやCIへ掲載しません。
