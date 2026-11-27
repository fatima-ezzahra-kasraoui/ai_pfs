package ma.agentshield.audit;

import java.util.Map;
import org.springframework.http.HttpStatus;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

/** Read-only projection of stored security events (not an invented user activity log). */
@RestController
public class AuditReadController {
    private final JdbcTemplate db;

    public AuditReadController(JdbcTemplate db) { this.db = db; }

    @GetMapping("/api/audit/events")
    @PreAuthorize("hasAnyRole('ANALYST', 'ADMIN')")
    public Map<String, Object> list(@RequestParam(defaultValue = "0") int page,
            @RequestParam(defaultValue = "20") int size,
            @RequestParam(defaultValue = "") String search,
            @RequestParam(defaultValue = "") String module,
            @RequestParam(defaultValue = "") String decision) {
        if (page < 0 || size < 1 || size > 100 || search.length() > 200) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Filtres invalides.");
        }
        String where = " FROM events WHERE (? = '' OR module = ?) AND (? = '' OR decision = ?)"
                + " AND (? = '' OR strpos(lower(concat_ws(' ', id::text, attack_type, correlation_id, simulation_id::text)), lower(?)) > 0)";
        Long total = db.queryForObject("SELECT count(*)" + where, Long.class, module, module, decision, decision, search, search);
        var items = db.queryForList("SELECT id::text AS id, occurred_at AS timestamp, 'Non renseigne' AS actor,"
                + " attack_type AS action, module, decision, risk_level AS result, coalesce(correlation_id, simulation_id::text, id::text) AS reference"
                + where + " ORDER BY occurred_at DESC, id LIMIT ? OFFSET ?", module, module, decision, decision, search, search, size, (long) page * size);
        return Map.of("items", items, "page", page, "size", size, "total", total);
    }
}
