package ma.agentshield.integration;

import com.sun.net.httpserver.Headers;
import com.sun.net.httpserver.HttpServer;
import java.io.IOException;
import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.concurrent.CopyOnWriteArrayList;

/** Faux service IA (serveur HTTP du JDK) : repond a la demande, peut etre lent, enregistre les requetes recues. */
final class FakeAiService implements AutoCloseable {

    record Recorded(String method, String path, Headers headers, String body) {
    }

    final List<Recorded> requests = new CopyOnWriteArrayList<>();
    private final HttpServer server;

    FakeAiService() throws IOException {
        server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        server.start();
    }

    String baseUrl() {
        return "http://127.0.0.1:" + server.getAddress().getPort();
    }

    void respond(String path, int status, String json) {
        respondAfter(path, 0, status, json);
    }

    void respondAfter(String path, long delayMillis, int status, String json) {
        server.createContext(path, exchange -> {
            String body = new String(exchange.getRequestBody().readAllBytes(), StandardCharsets.UTF_8);
            requests.add(new Recorded(exchange.getRequestMethod(), exchange.getRequestURI().getPath(),
                    exchange.getRequestHeaders(), body));
            try {
                if (delayMillis > 0) {
                    Thread.sleep(delayMillis);
                }
                byte[] bytes = json.getBytes(StandardCharsets.UTF_8);
                exchange.getResponseHeaders().add("Content-Type", "application/json");
                exchange.sendResponseHeaders(status, bytes.length);
                try (OutputStream out = exchange.getResponseBody()) {
                    out.write(bytes);
                }
            } catch (IOException | InterruptedException ignored) {
                // le client a deja abandonne (timeout) : rien a faire
            }
        });
    }

    @Override
    public void close() {
        server.stop(0);
    }
}
