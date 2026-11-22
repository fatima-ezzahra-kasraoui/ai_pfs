package ma.agentshield.db;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.util.ArrayList;
import java.util.List;
import org.flywaydb.core.Flyway;
import org.flywaydb.core.api.output.MigrateResult;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.testcontainers.containers.PostgreSQLContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;

/** AS-S1-016 : la migration V1 s'applique sur une base VIDE et la base refuse les valeurs hors contrat. */
@Testcontainers
class FlywayMigrationTest {

    @Container
    static final PostgreSQLContainer<?> POSTGRES = new PostgreSQLContainer<>("postgres:16-alpine");

    @BeforeAll
    static void migrate() {
        MigrateResult result = Flyway.configure()
                .dataSource(POSTGRES.getJdbcUrl(), POSTGRES.getUsername(), POSTGRES.getPassword())
                .load()
                .migrate();
        assertThat(result.success).isTrue();
        assertThat(result.migrationsExecuted).isEqualTo(1);
    }

    private static Connection connect() throws SQLException {
        return DriverManager.getConnection(POSTGRES.getJdbcUrl(), POSTGRES.getUsername(), POSTGRES.getPassword());
    }

    private static void exec(String sql) throws SQLException {
        try (Connection c = connect(); PreparedStatement ps = c.prepareStatement(sql)) {
            ps.executeUpdate();
        }
    }

    @Test
    void createsTheFourTables() throws SQLException {
        List<String> tables = new ArrayList<>();
        try (Connection c = connect();
                PreparedStatement ps = c.prepareStatement(
                        "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'");
                ResultSet rs = ps.executeQuery()) {
            while (rs.next()) {
                tables.add(rs.getString(1));
            }
        }
        assertThat(tables).contains("users", "simulations", "events", "approvals");
    }

    @Test
    void createsTheEventIndexes() throws SQLException {
        List<String> indexes = new ArrayList<>();
        try (Connection c = connect();
                PreparedStatement ps = c.prepareStatement("SELECT indexname FROM pg_indexes WHERE tablename = 'events'");
                ResultSet rs = ps.executeQuery()) {
            while (rs.next()) {
                indexes.add(rs.getString(1));
            }
        }
        assertThat(indexes).contains("idx_events_occurred_at", "idx_events_decision", "idx_events_module");
    }

    @Test
    void acceptsAllThreeRoles() {
        for (String role : List.of("ANALYST", "APPROVER", "ADMIN")) {
            String sql = "INSERT INTO users (username, password_hash, role) VALUES ('ok-" + role + "', 'hash', '" + role + "')";
            org.junit.jupiter.api.Assertions.assertDoesNotThrow(() -> exec(sql));
        }
    }

    @Test
    void rejectsARoleOutsideTheThreeAllowed() {
        assertThatThrownBy(() -> exec("INSERT INTO users (username, password_hash, role) VALUES ('x', 'hash', 'SUPERUSER')"))
                .isInstanceOf(SQLException.class)
                .hasMessageContaining("ck_users_role");
    }

    @Test
    void rejectsADuplicateUsername() throws SQLException {
        exec("INSERT INTO users (username, password_hash, role) VALUES ('dup', 'hash', 'ANALYST')");
        assertThatThrownBy(() -> exec("INSERT INTO users (username, password_hash, role) VALUES ('dup', 'hash', 'ADMIN')"))
                .isInstanceOf(SQLException.class)
                .hasMessageContaining("uq_users_username");
    }

    @Test
    void rejectsAnEventWithAScoreOutsideZeroOne() {
        assertThatThrownBy(() -> exec("INSERT INTO events (module, attack_type, decision, risk_level, score, reason)"
                        + " VALUES ('A', 'none', 'ALLOW', 'low', 1.5, 'r')"))
                .isInstanceOf(SQLException.class)
                .hasMessageContaining("ck_events_score");
    }

    @Test
    void rejectsAnUnknownDecisionAndAttackType() {
        assertThatThrownBy(() -> exec("INSERT INTO events (module, attack_type, decision, risk_level, score, reason)"
                        + " VALUES ('A', 'none', 'MAYBE', 'low', 0.1, 'r')"))
                .hasMessageContaining("ck_events_decision");
        assertThatThrownBy(() -> exec("INSERT INTO events (module, attack_type, decision, risk_level, score, reason)"
                        + " VALUES ('A', 'sql_injection', 'ALLOW', 'low', 0.1, 'r')"))
                .hasMessageContaining("ck_events_attack_type");
    }

    @Test
    void rejectsAnUnknownSimulationStatus() {
        assertThatThrownBy(() -> exec("INSERT INTO simulations (scenario_id, status) VALUES ('scenario-1', 'PAUSED')"))
                .hasMessageContaining("ck_simulations_status");
    }

    @Test
    void enforcesTheForeignKeyFromApprovalsToSimulations() {
        assertThatThrownBy(() -> exec("INSERT INTO approvals (status, tool_name, parameters_hash, risk_level, reason, simulation_id, expires_at)"
                        + " VALUES ('PENDING', 'delete_file', 'abc', 'high', 'r', gen_random_uuid(), now() + interval '1 hour')"))
                .hasMessageContaining("approvals_simulation_id_fkey");
    }
}
