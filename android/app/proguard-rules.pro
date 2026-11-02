# WebView'daki sayfanın çağırdığı köprü metotları (TekTiklaAndroid.*): adları küçültülmemeli
-keepclassmembers class * {
    @android.webkit.JavascriptInterface <methods>;
}
-keepattributes JavascriptInterface
