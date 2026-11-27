package ma.agentshield.integration;

import com.fasterxml.jackson.databind.JsonNode;
import java.util.List;
import java.util.Map;
import org.springframework.boot.actuate.health.HealthEndpoint;
import org.springframework.http.HttpStatus;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientException;
import org.springframework.web.server.ResponseStatusException;

@RestController
public class SystemReadController {
    private final RestClient ai;
    private final HealthEndpoint health;
    private final JdbcTemplate db;

    public SystemReadController(AiServiceProperties properties, HealthEndpoint health, JdbcTemplate db) {
        var factory = new SimpleClientHttpRequestFactory();
        factory.setConnectTimeout(3000);
        factory.setReadTimeout(5000);
        this.ai = RestClient.builder().baseUrl(properties.baseUrl()).requestFactory(factory)
                .defaultHeader("X-AI-Service-Key", properties.serviceKey()).build();
        this.health = health;
        this.db = db;
    }

    @GetMapping("/api/system/services")
    public Map<String, Object> services() {
        String database;
        try { db.queryForObject("SELECT 1", Integer.class); database = "UP"; }
        catch (RuntimeException ex) { database = "DOWN"; }
        String backend = "UP".equals(health.health().getStatus().getCode()) ? "UP" : "DEGRADED";
        String aiStatus = "DOWN";
        try {
            JsonNode data = read("/internal/health");
            if ("ok".equals(data.path("status").asText())) {
                boolean degraded = !data.path("agent").path("available").asBoolean()
                        || data.path("agent").path("simulated").asBoolean()
                        || data.path("stub").asBoolean() || data.path("policy").path("reloadFailed").asBoolean();
                for (JsonNode guard : data.path("degraded")) { degraded |= guard.asBoolean(); }
                aiStatus = degraded ? "DEGRADED" : "UP";
            }
        } catch (ResponseStatusException ex) { /* no upstream evidence */ }
        return Map.of("status", "UP".equals(backend) && "UP".equals(database) && "UP".equals(aiStatus) ? "UP" : "DEGRADED",
                "services", List.of(Map.of("name", "Backend", "status", backend),
                        Map.of("name", "PostgreSQL", "status", database),
                        Map.of("name", "Service IA", "status", aiStatus,
                                "detail", "Sonde du service, pas un test d'inference")));
    }

    @GetMapping("/api/analytics/metrics")
    public JsonNode metrics() { return read("/internal/metrics"); }

    @GetMapping("/api/policy")
    public JsonNode policy() { return read("/internal/policy"); }

    private JsonNode read(String path) {
        try {
            JsonNode result = ai.get().uri(path).retrieve().body(JsonNode.class);
            if (result == null || !result.isObject()) { throw new ResponseStatusException(HttpStatus.BAD_GATEWAY); }
            return result;
        } catch (RestClientException ex) {
            throw new ResponseStatusException(HttpStatus.BAD_GATEWAY, "Service IA indisponible.");
        }
    }
}
