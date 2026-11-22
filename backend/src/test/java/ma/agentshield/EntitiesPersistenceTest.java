package ma.agentshield;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.List;
import ma.agentshield.approvals.Approval;
import ma.agentshield.approvals.ApprovalRepository;
import ma.agentshield.approvals.ApprovalStatus;
import ma.agentshield.auth.Role;
import ma.agentshield.auth.UserAccount;
import ma.agentshield.auth.UserAccountRepository;
import ma.agentshield.events.Decision;
import ma.agentshield.events.Event;
import ma.agentshield.events.EventRepository;
import ma.agentshield.events.GuardModule;
import ma.agentshield.simulations.Simulation;
import ma.agentshield.simulations.SimulationRepository;
import ma.agentshield.simulations.SimulationStatus;
import ma.agentshield.support.PostgresTestConfig;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.jdbc.AutoConfigureTestDatabase;
import org.springframework.boot.test.autoconfigure.orm.jpa.DataJpaTest;
import org.springframework.context.annotation.Import;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.test.context.ActiveProfiles;

/**
 * AS-S1-017 : lecture et ecriture sur chaque entite, sur un vrai PostgreSQL.
 * {@code ddl-auto=validate} fait aussi echouer ce test si une entite ne correspond pas a la migration V1.
 */
@DataJpaTest
@AutoConfigureTestDatabase(replace = AutoConfigureTestDatabase.Replace.NONE)
@Import(PostgresTestConfig.class)
@ActiveProfiles("test")
class EntitiesPersistenceTest {

    @Autowired
    private UserAccountRepository users;

    @Autowired
    private SimulationRepository simulations;

    @Autowired
    private EventRepository events;

    @Autowired
    private ApprovalRepository approvals;

    @Test
    void userRoundTrip() {
        UserAccount saved = users.saveAndFlush(new UserAccount("alice", "hash-bcrypt", Role.APPROVER, "alice@exemple.test"));

        UserAccount found = users.findByUsername("alice").orElseThrow();
        assertThat(found.getId()).isEqualTo(saved.getId()).isNotNull();
        assertThat(found.getRole()).isEqualTo(Role.APPROVER);
        assertThat(found.isEnabled()).isTrue();
        assertThat(found.getCreatedAt()).isNotNull();
        assertThat(users.existsByUsername("alice")).isTrue();
        assertThat(users.findByUsername("inconnu")).isEmpty();
    }

    @Test
    void usernameMustBeUnique() {
        users.saveAndFlush(new UserAccount("bob", "h1", Role.ANALYST, null));
        assertThatThrownBy(() -> users.saveAndFlush(new UserAccount("bob", "h2", Role.ADMIN, null)))
                .isInstanceOf(DataIntegrityViolationException.class);
    }

    @Test
    void simulationRoundTripWithResultJson() {
        Simulation sim = new Simulation("scenario-1", null);
        sim.setResultJson("{\"unprotected\":{\"attackSucceeded\":true}}");
        Simulation saved = simulations.saveAndFlush(sim);

        Simulation found = simulations.findById(saved.getId()).orElseThrow();
        assertThat(found.getStatus()).isEqualTo(SimulationStatus.SUBMITTED);
        assertThat(found.getScenarioId()).isEqualTo("scenario-1");
        assertThat(found.getResultJson()).contains("attackSucceeded");
        assertThat(found.getCompletedAt()).isNull();
    }

    @Test
    void simulationStatusCanBeUpdated() {
        Simulation sim = simulations.saveAndFlush(new Simulation("scenario-2", null));
        sim.setStatus(SimulationStatus.FAILED);
        sim.setError("Service IA indisponible.");
        sim.setCompletedAt(Instant.now());
        simulations.saveAndFlush(sim);

        Simulation found = simulations.findById(sim.getId()).orElseThrow();
        assertThat(found.getStatus()).isEqualTo(SimulationStatus.FAILED);
        assertThat(found.getError()).isEqualTo("Service IA indisponible.");
    }

    @Test
    void eventRoundTripKeepsMaskedExcerptAndContractValues() {
        Simulation sim = simulations.saveAndFlush(new Simulation("scenario-1", null));
        Event event = new Event(GuardModule.A, "direct_injection", Decision.BLOCK, "high", 0.97, "motif de jailbreak");
        event.setSimulationId(sim.getId());
        event.setCorrelationId("corr-123");
        event.setExcerpt("Ignore toutes les [MASQUE]");
        Event saved = events.saveAndFlush(event);

        Event found = events.findById(saved.getId()).orElseThrow();
        assertThat(found.getModule()).isEqualTo(GuardModule.A);
        assertThat(found.getAttackType()).isEqualTo("direct_injection");
        assertThat(found.getDecision()).isEqualTo(Decision.BLOCK);
        assertThat(found.getRiskLevel()).isEqualTo("high");
        assertThat(found.getScore()).isEqualTo(0.97);
        assertThat(found.getExcerpt()).isEqualTo("Ignore toutes les [MASQUE]");
        assertThat(found.getOccurredAt()).isNotNull();
        assertThat(events.findBySimulationIdOrderByOccurredAtAsc(sim.getId())).hasSize(1);
        assertThat(events.countByDecision(Decision.BLOCK)).isEqualTo(1);
    }

    @Test
    void eventWithAnUnknownAttackTypeIsRejectedByTheDatabase() {
        Event bad = new Event(GuardModule.B, "sql_injection", Decision.ALLOW, "low", 0.1, "r");
        assertThatThrownBy(() -> events.saveAndFlush(bad)).isInstanceOf(DataIntegrityViolationException.class);
    }

    @Test
    void approvalRoundTripAndFilterByStatus() {
        Approval a = new Approval("delete_file", "a".repeat(64), "high", "suppression demandee",
                Instant.now().plus(15, ChronoUnit.MINUTES));
        a.setParametersJson("{\"path\":\"/tmp/x\"}");
        Approval saved = approvals.saveAndFlush(a);

        Approval found = approvals.findById(saved.getId()).orElseThrow();
        assertThat(found.getStatus()).isEqualTo(ApprovalStatus.PENDING);
        assertThat(found.getParametersHash()).hasSize(64);
        assertThat(found.getDecidedAt()).isNull();

        List<Approval> pending = approvals.findByStatusOrderByCreatedAtDesc(ApprovalStatus.PENDING);
        assertThat(pending).extracting(Approval::getId).contains(saved.getId());
        assertThat(approvals.findByStatusOrderByCreatedAtDesc(ApprovalStatus.APPROVED)).isEmpty();
    }
}
