package ma.agentshield.analytics;

import java.util.LinkedHashMap;
import java.util.Map;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

/** Aggregats des verdicts effectivement persistés, sans estimation de l'ASR. */
@RestController
public class OverviewController {
    private final JdbcTemplate db;

    public OverviewController(JdbcTemplate db) { this.db = db; }

    @GetMapping("/api/dashboard/overview")
    public Map<String, Object> overview() {
        Map<String, Object> data = new LinkedHashMap<>();
        // Les verdicts ne représentent pas nécessairement des requêtes uniques.
        data.put("totalRequests", null);
        data.put("attacksDetected", count("SELECT count(*) FROM events WHERE attack_type <> 'none'"));
        data.put("blockedActions", count("SELECT count(*) FROM events WHERE decision = 'BLOCK'"));
        data.put("sanitizedActions", count("SELECT count(*) FROM events WHERE decision = 'SANITIZE'"));
        data.put("pendingConfirmations", count("SELECT count(*) FROM approvals WHERE status = 'PENDING' AND expires_at > now()"));
        data.put("asr", null);
        data.put("attacksOverTime", db.queryForList("SELECT to_char(occurred_at AT TIME ZONE 'UTC', 'YYYY-MM-DD') AS date, count(*) AS count FROM events WHERE attack_type <> 'none' GROUP BY 1 ORDER BY 1"));
        data.put("decisions", grouped("SELECT decision AS label, count(*) AS n FROM events GROUP BY decision"));
        data.put("byCategory", grouped("SELECT attack_type AS label, count(*) AS n FROM events WHERE attack_type <> 'none' GROUP BY attack_type"));
        data.put("bySeverity", grouped("SELECT risk_level AS label, count(*) AS n FROM events WHERE attack_type <> 'none' GROUP BY risk_level"));
        data.put("recent", db.queryForList("SELECT id::text AS id, occurred_at AS timestamp, module, decision, attack_type AS \"attackType\", attack_type AS summary FROM events ORDER BY occurred_at DESC, id LIMIT 20"));
        return data;
    }

    private Long count(String sql) { return db.queryForObject(sql, Long.class); }
    private Map<String, Long> grouped(String sql) {
        Map<String, Long> result = new LinkedHashMap<>();
        db.query(sql, rs -> { result.put(rs.getString("label"), rs.getLong("n")); });
        return result;
    }
}
