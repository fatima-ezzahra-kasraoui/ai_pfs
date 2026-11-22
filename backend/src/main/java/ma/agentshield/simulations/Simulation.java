package ma.agentshield.simulations;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import java.time.Instant;
import java.util.UUID;

/** Une simulation : un scenario joue sans puis avec protection. */
@Entity
@Table(name = "simulations")
public class Simulation {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    private UUID id;

    @Column(name = "scenario_id", nullable = false, length = 40)
    private String scenarioId;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false, length = 20)
    private SimulationStatus status = SimulationStatus.SUBMITTED;

    @Column(name = "created_by")
    private UUID createdBy;

    @Column(name = "created_at", nullable = false, updatable = false)
    private Instant createdAt = Instant.now();

    @Column(name = "completed_at")
    private Instant completedAt;

    /** Message generique si FAILED : jamais de detail interne. */
    @Column(length = 200)
    private String error;

    /** Resultats des executions sans / avec protection, serialises en JSON. */
    @Column(name = "result_json", columnDefinition = "text")
    private String resultJson;

    protected Simulation() {
        // requis par JPA
    }

    public Simulation(String scenarioId, UUID createdBy) {
        this.scenarioId = scenarioId;
        this.createdBy = createdBy;
    }

    public UUID getId() {
        return id;
    }

    public String getScenarioId() {
        return scenarioId;
    }

    public SimulationStatus getStatus() {
        return status;
    }

    public void setStatus(SimulationStatus status) {
        this.status = status;
    }

    public UUID getCreatedBy() {
        return createdBy;
    }

    public Instant getCreatedAt() {
        return createdAt;
    }

    public Instant getCompletedAt() {
        return completedAt;
    }

    public void setCompletedAt(Instant completedAt) {
        this.completedAt = completedAt;
    }

    public String getError() {
        return error;
    }

    public void setError(String error) {
        this.error = error;
    }

    public String getResultJson() {
        return resultJson;
    }

    public void setResultJson(String resultJson) {
        this.resultJson = resultJson;
    }
}
