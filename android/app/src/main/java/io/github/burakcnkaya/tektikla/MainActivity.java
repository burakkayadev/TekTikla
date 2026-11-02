package io.github.burakcnkaya.tektikla;

import android.annotation.SuppressLint;
import android.content.ActivityNotFoundException;
import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.ContentResolver;
import android.content.ContentValues;
import android.content.Intent;
import android.content.SharedPreferences;
import android.graphics.Color;
import android.net.ConnectivityManager;
import android.net.LinkAddress;
import android.net.LinkProperties;
import android.net.Network;
import android.net.NetworkCapabilities;
import android.net.Uri;
import android.os.Bundle;
import android.os.Environment;
import android.os.Handler;
import android.os.Looper;
import android.provider.MediaStore;
import android.webkit.JavascriptInterface;
import android.webkit.MimeTypeMap;
import android.webkit.URLUtil;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.FrameLayout;
import android.widget.Toast;

import androidx.activity.ComponentActivity;
import androidx.activity.EdgeToEdge;
import androidx.activity.OnBackPressedCallback;
import androidx.activity.SystemBarStyle;
import androidx.activity.result.ActivityResultLauncher;
import androidx.activity.result.contract.ActivityResultContracts;
import androidx.core.graphics.Insets;
import androidx.core.view.ViewCompat;
import androidx.core.view.WindowCompat;
import androidx.core.view.WindowInsetsCompat;
import androidx.core.view.WindowInsetsControllerCompat;

import com.journeyapps.barcodescanner.ScanContract;
import com.journeyapps.barcodescanner.ScanOptions;

import org.json.JSONObject;

import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.Inet4Address;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicReference;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * TekTıkla'nın Android uygulaması: bilgisayardaki TekTıkla'nın telefon sayfasını (tektikla/remote.py, web/remote.js)
 * tam ekran açar. İşleri yine bilgisayar yapar; uygulama QR kodla bağlanmayı, başka uygulamalardan paylaşılan linki
 * bilgisayara iletmeyi, telefondan dosya seçmeyi ve sonuçları Galeri'ye kaydetmeyi sağlar.
 */
public class MainActivity extends ComponentActivity {
    private static final String START = "file:///android_asset/start.html";
    private static final int PORT = 8790;
    private static final String PREFS = "tektikla";
    private static final Pattern LINK = Pattern.compile("https?://\\S+");
    // bilgisayardaki QR kodun adresi: http://192.168.1.34:8790/#k=ABCDE12345
    private static final Pattern QR = Pattern.compile(
            "^https?://([A-Za-z0-9.-]+):(\\d{2,5})/?(?:\\?[^#]*)?#(?:.*&)?k=([A-Za-z0-9-]{10,11})");
    private static final Pattern ADDRESS = Pattern.compile("^(?:https?://)?([A-Za-z0-9.-]+)(?::(\\d{2,5}))?/?$");

    private final Handler ui = new Handler(Looper.getMainLooper());
    private final ExecutorService io = Executors.newCachedThreadPool();
    private FrameLayout root;
    private WebView web;
    private volatile Server server;  // sayfası açık olan bilgisayar
    private String shared;  // başka uygulamadan paylaşılan, bilgisayara iletilecek link
    private ValueCallback<Uri[]> files;

    private final ActivityResultLauncher<ScanOptions> scanner =
            registerForActivityResult(new ScanContract(), result -> onScanned(result.getContents()));
    private final ActivityResultLauncher<Intent> picker =
            registerForActivityResult(new ActivityResultContracts.StartActivityForResult(),
                    result -> onPicked(result.getResultCode(), result.getData()));

    /** Bağlanılan bilgisayar: ev ağındaki adresi ve bağlanma kodu. */
    static final class Server {
        final String host;
        final int port;
        final String key;

        Server(String host, int port, String key) {
            this.host = host;
            this.port = port;
            this.key = key;
        }

        String base() {
            return "http://" + host + ":" + port;
        }

        static Server parse(String text) {
            Matcher m = text == null ? null : QR.matcher(text.trim());
            return m != null && m.find() ? new Server(m.group(1), Integer.parseInt(m.group(2)), clean(m.group(3))) : null;
        }
    }

    static String clean(String code) {
        return code == null ? "" : code.toUpperCase(Locale.ROOT).replaceAll("[^A-Z0-9]", "");
    }

    // ------------------------------------------------------------------ açılış
    @SuppressLint("SetJavaScriptEnabled")
    @Override
    protected void onCreate(Bundle state) {
        EdgeToEdge.enable(this, SystemBarStyle.dark(Color.TRANSPARENT), SystemBarStyle.dark(Color.TRANSPARENT));
        super.onCreate(state);
        root = new FrameLayout(this);
        root.setBackgroundColor(0xFF050505);
        web = new WebView(this);
        web.setBackgroundColor(0xFF050505);
        root.addView(web, new FrameLayout.LayoutParams(FrameLayout.LayoutParams.MATCH_PARENT, FrameLayout.LayoutParams.MATCH_PARENT));
        setContentView(root);
        // durum çubuğu, gezinme çubuğu ve klavye sayfanın üstüne binmesin
        ViewCompat.setOnApplyWindowInsetsListener(root, (v, insets) -> {
            Insets bars = insets.getInsets(WindowInsetsCompat.Type.systemBars() | WindowInsetsCompat.Type.displayCutout()
                    | WindowInsetsCompat.Type.ime());
            v.setPadding(bars.left, bars.top, bars.right, bars.bottom);
            return WindowInsetsCompat.CONSUMED;
        });

        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setAllowFileAccess(false);  // yerel karşılama sayfası (android_asset) bundan etkilenmez
        s.setAllowContentAccess(true);  // seçilen dosyaların content:// adresleri
        s.setMediaPlaybackRequiresUserGesture(false);
        s.setUserAgentString(s.getUserAgentString() + " TekTiklaAndroid/" + BuildConfig.VERSION_NAME);
        WebView.setWebContentsDebuggingEnabled(BuildConfig.DEBUG);
        web.addJavascriptInterface(new Bridge(), "TekTiklaAndroid");
        web.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                return route(request.getUrl());
            }

            @Override
            public void onPageFinished(WebView view, String url) {
                if (shared != null && onServer(url)) deliverShare();
            }

            @Override
            public void onReceivedError(WebView view, WebResourceRequest request, WebResourceError error) {
                // bilgisayardaki sayfa açılamadı: bağlantıyı yeniden dene, gerekirse ağda ara
                if (request.isForMainFrame() && onServer(request.getUrl().toString())) start();
            }
        });
        web.setWebChromeClient(new WebChromeClient() {
            @Override
            public boolean onShowFileChooser(WebView view, ValueCallback<Uri[]> callback, FileChooserParams params) {
                return chooseFiles(callback, params);
            }
        });
        // sayfadaki sıradan indirme bağlantıları da telefona kaydedilir
        web.setDownloadListener((url, agent, disposition, mime, length) ->
                save(url, URLUtil.guessFileName(url, disposition, mime), null));

        getOnBackPressedDispatcher().addCallback(this, new OnBackPressedCallback(true) {
            @Override
            public void handleOnBackPressed() {
                // önce sayfa: açık pencereyi ya da menüyü kapatır, ana sayfaya döner; iş kalmadıysa uygulama arka plana alınır
                if (!onServer(web.getUrl())) {
                    finish();
                    return;
                }
                web.evaluateJavascript("window.ttBack ? ttBack() : false", handled -> {
                    if (!"true".equals(handled)) moveTaskToBack(true);
                });
            }
        });
        if (!handleIntent(getIntent())) start();
    }

    @Override
    protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        setIntent(intent);
        handleIntent(intent);
    }

    @Override
    protected void onPause() {
        web.onPause();
        super.onPause();
    }

    @Override
    protected void onResume() {
        super.onResume();
        web.onResume();
    }

    @Override
    protected void onDestroy() {
        io.shutdownNow();
        web.destroy();
        super.onDestroy();
    }

    /** Paylaşılan link ya da QR adresiyle açıldıysa onunla ilgilenir; sıradan açılışta false döner. */
    private boolean handleIntent(Intent intent) {
        if (intent == null) return false;
        if (Intent.ACTION_SEND.equals(intent.getAction())) {
            String text = intent.getStringExtra(Intent.EXTRA_TEXT);
            Matcher m = text == null ? null : LINK.matcher(text);
            if (m == null || !m.find()) return false;
            shared = m.group();
            if (onServer(web.getUrl())) deliverShare();
            else if (web.getUrl() == null) start();  // uygulama paylaşımla açıldı: önce bilgisayara bağlan
            return true;
        }
        if (Intent.ACTION_VIEW.equals(intent.getAction()) && intent.getData() != null) {
            Server s = Server.parse(intent.getData().toString());
            if (s != null) {
                connectTo(s);
                return true;
            }
        }
        return false;
    }

    private void deliverShare() {
        String url = shared;
        shared = null;
        web.evaluateJavascript("window.ttShare && ttShare(" + JSONObject.quote(url) + ")", null);
    }

    // ------------------------------------------------------------------ bağlantı
    private Server saved() {
        SharedPreferences p = getSharedPreferences(PREFS, MODE_PRIVATE);
        String host = p.getString("host", null), key = p.getString("key", null);
        return host == null || key == null ? null : new Server(host, p.getInt("port", PORT), key);
    }

    private void remember(Server s) {
        getSharedPreferences(PREFS, MODE_PRIVATE).edit()
                .putString("host", s.host).putInt("port", s.port).putString("key", s.key).apply();
    }

    private boolean onServer(String url) {
        Server s = server;
        return s != null && url != null && (url.equals(s.base()) || url.startsWith(s.base() + "/"));
    }

    /** Karşılama sayfası: first, connecting, searching, net, key, wifi, bad, badqr. */
    private void page(String state) {
        web.loadUrl(START + "?s=" + state);
    }

    private void open(Server s) {
        server = s;
        web.loadUrl(s.base() + "/#k=" + s.key);  // remote.js kodu saklar ve adresten siler
    }

    /** Kayıtlı bilgisayara bağlanır; adresi değiştiyse (ev ağında yeni IP) aynı ağda arar. */
    private void start() {
        Server s = saved();
        if (s == null) {
            page("first");
            return;
        }
        page("connecting");
        io.execute(() -> {
            int code = hello(s, 2500);
            if (code == 200) {
                ui.post(() -> open(s));
            } else if (code == 401) {
                ui.post(() -> page("key"));
            } else if (!onLocalNetwork()) {
                ui.post(() -> page("wifi"));
            } else {
                ui.post(() -> page("searching"));
                Server found = discover(s);
                ui.post(() -> {
                    if (found == null) {
                        page("net");
                        return;
                    }
                    remember(found);
                    open(found);
                });
            }
        });
    }

    private void connectTo(Server s) {
        page("connecting");
        io.execute(() -> {
            int code = hello(s, 3000);
            ui.post(() -> {
                if (code == 200) {
                    remember(s);
                    open(s);
                } else {
                    page(code == 401 ? "key" : "net");
                }
            });
        });
    }

    /** Bilgisayardaki TekTıkla'ya kodla "merhaba" der: 200 bağlandı, 401 kod yanlış, -1 ulaşılamadı. */
    static int hello(Server s, int timeout) {
        HttpURLConnection c = null;
        try {
            c = (HttpURLConnection) new URL(s.base() + "/api/remote_hello").openConnection();
            c.setConnectTimeout(timeout);
            c.setReadTimeout(timeout + 2000);
            c.setRequestMethod("POST");
            c.setDoOutput(true);
            c.setRequestProperty("X-TekTikla-Key", s.key);
            c.setRequestProperty("Content-Type", "application/json");
            try (OutputStream out = c.getOutputStream()) {
                out.write("[]".getBytes(StandardCharsets.UTF_8));
            }
            return c.getResponseCode();
        } catch (IOException | RuntimeException e) {
            return -1;
        } finally {
            if (c != null) c.disconnect();
        }
    }

    /** Aynı ağdaki adresleri (ör. 192.168.1.1–254) kayıtlı kodla dener; bilgisayarın yeni adresini bulur. */
    private Server discover(Server s) {
        String prefix = subnet();
        if (prefix == null) return null;
        int[] ports = s.port == PORT ? new int[]{PORT} : new int[]{s.port, PORT};
        ExecutorService pool = Executors.newFixedThreadPool(48);
        AtomicReference<Server> found = new AtomicReference<>();
        for (int i = 1; i < 255; i++) {
            for (int port : ports) {
                Server candidate = new Server(prefix + i, port, s.key);
                pool.execute(() -> {
                    if (found.get() == null && hello(candidate, 700) == 200) found.compareAndSet(null, candidate);
                });
            }
        }
        pool.shutdown();
        try {
            pool.awaitTermination(25, TimeUnit.SECONDS);
        } catch (InterruptedException ignored) {
            Thread.currentThread().interrupt();
        }
        pool.shutdownNow();
        return found.get();
    }

    private String subnet() {
        ConnectivityManager cm = getSystemService(ConnectivityManager.class);
        Network net = cm == null ? null : cm.getActiveNetwork();
        LinkProperties lp = net == null ? null : cm.getLinkProperties(net);
        if (lp == null) return null;
        for (LinkAddress a : lp.getLinkAddresses()) {
            if (a.getAddress() instanceof Inet4Address && !a.getAddress().isLoopbackAddress()) {
                String ip = a.getAddress().getHostAddress();
                return ip == null ? null : ip.substring(0, ip.lastIndexOf('.') + 1);
            }
        }
        return null;
    }

    private boolean onLocalNetwork() {
        ConnectivityManager cm = getSystemService(ConnectivityManager.class);
        NetworkCapabilities c = cm == null ? null : cm.getNetworkCapabilities(cm.getActiveNetwork());
        return c != null && (c.hasTransport(NetworkCapabilities.TRANSPORT_WIFI)
                || c.hasTransport(NetworkCapabilities.TRANSPORT_ETHERNET));
    }

    // ------------------------------------------------------------------ QR kod
    private void scan() {
        ScanOptions o = new ScanOptions();
        o.setDesiredBarcodeFormats(ScanOptions.QR_CODE);
        o.setPrompt(getString(R.string.scan_prompt));
        o.setBeepEnabled(false);
        o.setOrientationLocked(false);
        scanner.launch(o);
    }

    private void onScanned(String text) {
        if (text == null) return;  // tarayıcıdan geri dönüldü
        Server s = Server.parse(text);
        if (s == null) page("badqr");
        else connectTo(s);
    }

    // ------------------------------------------------------------------ bağlantılar
    private boolean route(Uri uri) {
        String url = uri.toString();
        if ("file".equals(uri.getScheme())) return false;
        if (onServer(url)) {
            String path = uri.getPath() == null ? "" : uri.getPath();
            if (path.startsWith("/f/") || path.startsWith("/m/")) {
                view(url);  // bilgisayardaki dosya: telefondaki oynatıcıda ya da tarayıcıda
                return true;
            }
            return false;
        }
        Server s = Server.parse(url);
        if (s != null) connectTo(s);
        else openOut(url);
        return true;
    }

    private void view(String url) {
        String name = Uri.parse(url).getLastPathSegment();
        String mime = name == null ? null : mimeOf(name);
        Intent i = new Intent(Intent.ACTION_VIEW).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        if (mime != null && !mime.startsWith("application/")) i.setDataAndType(Uri.parse(url), mime);
        else i.setData(Uri.parse(url));
        try {
            startActivity(i);
        } catch (ActivityNotFoundException e) {
            openOut(url);
        }
    }

    private void openOut(String url) {
        try {
            startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(url)).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));
        } catch (ActivityNotFoundException e) {
            Toast.makeText(this, R.string.no_app, Toast.LENGTH_SHORT).show();
        }
    }

    // ------------------------------------------------------------------ telefondan dosya seçme
    private boolean chooseFiles(ValueCallback<Uri[]> callback, WebChromeClient.FileChooserParams params) {
        if (files != null) files.onReceiveValue(null);
        files = callback;
        List<String> types = new ArrayList<>();
        boolean any = false;
        for (String accept : params.getAcceptTypes()) {
            for (String part : accept.split(",")) {
                part = part.trim().toLowerCase(Locale.ROOT);
                if (part.isEmpty()) continue;
                String mime = part.startsWith(".") ? MimeTypeMap.getSingleton().getMimeTypeFromExtension(part.substring(1)) : part;
                if (mime == null) any = true;  // tanınmayan uzantı (ör. .ass): her dosya seçilebilsin
                else if (!types.contains(mime)) types.add(mime);
            }
        }
        Intent i = new Intent(Intent.ACTION_GET_CONTENT).addCategory(Intent.CATEGORY_OPENABLE);
        if (any || types.isEmpty()) {
            i.setType("*/*");
        } else if (types.size() == 1) {
            i.setType(types.get(0));
        } else {
            i.setType("*/*");
            i.putExtra(Intent.EXTRA_MIME_TYPES, types.toArray(new String[0]));
        }
        i.putExtra(Intent.EXTRA_ALLOW_MULTIPLE, params.getMode() == WebChromeClient.FileChooserParams.MODE_OPEN_MULTIPLE);
        try {
            picker.launch(i);
            return true;
        } catch (ActivityNotFoundException e) {
            files = null;
            return false;
        }
    }

    private void onPicked(int code, Intent data) {
        if (files == null) return;
        Uri[] out = null;
        if (code == RESULT_OK && data != null) {
            ClipData clip = data.getClipData();
            if (clip != null) {
                out = new Uri[clip.getItemCount()];
                for (int i = 0; i < out.length; i++) out[i] = clip.getItemAt(i).getUri();
            } else if (data.getData() != null) {
                out = new Uri[]{data.getData()};
            }
        }
        files.onReceiveValue(out);
        files = null;
    }

    // ------------------------------------------------------------------ telefona kaydetme
    static String mimeOf(String name) {
        int dot = name.lastIndexOf('.');
        String ext = dot < 0 ? "" : name.substring(dot + 1).toLowerCase(Locale.ROOT);
        String mime = MimeTypeMap.getSingleton().getMimeTypeFromExtension(ext);
        return mime == null ? "application/octet-stream" : mime;
    }

    /** Bilgisayardaki dosyayı indirir: video ve resim Galeri'ye, ses Müzik'e, diğerleri İndirilenler'e (TekTıkla klasörü). */
    private void save(String url, String name, String id) {
        io.execute(() -> {
            String mime = mimeOf(name);
            Uri collection;
            String dir;
            int where;
            if (mime.startsWith("video/")) {
                collection = MediaStore.Video.Media.getContentUri(MediaStore.VOLUME_EXTERNAL_PRIMARY);
                dir = Environment.DIRECTORY_MOVIES;
                where = R.string.where_gallery;
            } else if (mime.startsWith("image/")) {
                collection = MediaStore.Images.Media.getContentUri(MediaStore.VOLUME_EXTERNAL_PRIMARY);
                dir = Environment.DIRECTORY_PICTURES;
                where = R.string.where_gallery;
            } else if (mime.startsWith("audio/")) {
                collection = MediaStore.Audio.Media.getContentUri(MediaStore.VOLUME_EXTERNAL_PRIMARY);
                dir = Environment.DIRECTORY_MUSIC;
                where = R.string.where_music;
            } else {
                collection = MediaStore.Downloads.getContentUri(MediaStore.VOLUME_EXTERNAL_PRIMARY);
                dir = Environment.DIRECTORY_DOWNLOADS;
                where = R.string.where_downloads;
            }
            ContentResolver cr = getContentResolver();
            ContentValues v = new ContentValues();
            v.put(MediaStore.MediaColumns.DISPLAY_NAME, name);
            v.put(MediaStore.MediaColumns.MIME_TYPE, mime);
            v.put(MediaStore.MediaColumns.RELATIVE_PATH, dir + "/TekTıkla");
            v.put(MediaStore.MediaColumns.IS_PENDING, 1);
            Uri item = null;
            HttpURLConnection c = null;
            try {
                item = cr.insert(collection, v);
                if (item == null) throw new IOException("insert");
                c = (HttpURLConnection) new URL(url).openConnection();
                c.setConnectTimeout(8000);
                c.setReadTimeout(60000);
                long total = c.getContentLengthLong(), done = 0, last = 0;
                try (InputStream in = c.getInputStream(); OutputStream out = cr.openOutputStream(item)) {
                    if (out == null) throw new IOException("open");
                    byte[] buf = new byte[1 << 16];
                    for (int n; (n = in.read(buf)) > 0; ) {
                        out.write(buf, 0, n);
                        done += n;
                        long now = System.currentTimeMillis();
                        if (id != null && now - last > 250) {
                            last = now;
                            progress(id, done, total, "run", "");
                        }
                    }
                }
                v.clear();
                v.put(MediaStore.MediaColumns.IS_PENDING, 0);
                cr.update(item, v, null, null);
                String label = getString(where);
                if (id != null) progress(id, done, done, "done", label);
                else ui.post(() -> Toast.makeText(this, getString(R.string.saved, label), Toast.LENGTH_LONG).show());
            } catch (IOException | RuntimeException e) {
                if (item != null) cr.delete(item, null, null);
                if (id != null) progress(id, 0, 0, "error", "");
                else ui.post(() -> Toast.makeText(this, R.string.save_failed, Toast.LENGTH_LONG).show());
            } finally {
                if (c != null) c.disconnect();
            }
        });
    }

    private void progress(String id, long done, long total, String state, String where) {
        String js = "window.ttSaved && ttSaved(" + JSONObject.quote(id) + "," + done + "," + total + ","
                + JSONObject.quote(state) + "," + JSONObject.quote(where) + ")";
        ui.post(() -> web.evaluateJavascript(js, null));
    }

    /** Sayfanın teması değişince sistem çubukları da aynı zemine boyanır. */
    private void bar(String css) {
        int color;
        try {
            Matcher m = Pattern.compile("(\\d+)\\D+(\\d+)\\D+(\\d+)").matcher(css);
            color = m.find() ? Color.rgb(Integer.parseInt(m.group(1)), Integer.parseInt(m.group(2)), Integer.parseInt(m.group(3)))
                    : Color.parseColor(css);
        } catch (RuntimeException e) {
            return;
        }
        root.setBackgroundColor(color);
        boolean light = Color.luminance(color) > 0.5f;
        WindowInsetsControllerCompat bars = WindowCompat.getInsetsController(getWindow(), getWindow().getDecorView());
        bars.setAppearanceLightStatusBars(light);
        bars.setAppearanceLightNavigationBars(light);
    }

    // ------------------------------------------------------------------ sayfanın kullandığı köprü
    /** Sayfadan TekTiklaAndroid.<ad>() olarak çağrılır (web/remote.js ve assets/start.html). */
    final class Bridge {
        @JavascriptInterface
        public void scan() {
            ui.post(MainActivity.this::scan);
        }

        @JavascriptInterface
        public void connect(String address, String code) {
            Matcher m = ADDRESS.matcher(address == null ? "" : address.trim());
            String key = clean(code);
            if (!m.find() || key.length() != 10) {
                ui.post(() -> page("bad"));
                return;
            }
            Server s = new Server(m.group(1), m.group(2) == null ? PORT : Integer.parseInt(m.group(2)), key);
            ui.post(() -> connectTo(s));
        }

        @JavascriptInterface
        public void retry() {
            ui.post(MainActivity.this::start);
        }

        @JavascriptInterface
        public void openExternal(String url) {
            if (url != null && url.matches("(?i)^https?://.+")) ui.post(() -> openOut(url));
        }

        @JavascriptInterface
        public void view(String url) {
            if (onServer(url)) ui.post(() -> MainActivity.this.view(url));
        }

        /** Telefona kaydetmeyi başlatır; ilerleme sayfaya ttSaved(id, …) ile bildirilir. */
        @JavascriptInterface
        public String save(String url, String name) {
            if (!onServer(url) || name == null) return "";
            String id = Long.toString(System.nanoTime(), 36);
            MainActivity.this.save(url, name.replaceAll("[\\\\/:*?\"<>|]", "_"), id);
            return id;
        }

        @JavascriptInterface
        public String paste() {
            AtomicReference<String> text = new AtomicReference<>("");
            CountDownLatch done = new CountDownLatch(1);
            ui.post(() -> {
                try {
                    ClipboardManager cm = getSystemService(ClipboardManager.class);
                    ClipData clip = cm == null ? null : cm.getPrimaryClip();
                    if (clip != null && clip.getItemCount() > 0) {
                        CharSequence t = clip.getItemAt(0).coerceToText(MainActivity.this);
                        text.set(t == null ? "" : t.toString());
                    }
                } finally {
                    done.countDown();
                }
            });
            try {
                done.await(2, TimeUnit.SECONDS);
            } catch (InterruptedException ignored) {
                Thread.currentThread().interrupt();
            }
            return text.get();
        }

        @JavascriptInterface
        public void setBar(String color) {
            if (color != null) ui.post(() -> bar(color));
        }

        @JavascriptInterface
        public String version() {
            return BuildConfig.VERSION_NAME;
        }
    }
}
