package ma.agentshield.events;

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

/**
 * Evenement de securite (un verdict). {@code attackType} et {@code riskLevel} gardent les valeurs du contrat
 * ({@code direct_injection}, {@code low}...), verifiees par des contraintes CHECK en base.
 */
@Entity
@Table(name = "events")
public class Event {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    private UUID id;

    @Column(name = "occurred_at", nullable = false)
    private Instant occurredAt = Instant.now();

    @Enumerated(EnumType.STRING)
    @Column(nullable = false, length = 10)
    private GuardModule module;

    @Column(name = "attack_type", nullable = false, length = 30)
    private String attackType;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false, length = 10)
    private Decision decision;

    @Column(name = "risk_level", nullable = false, length = 10)
    private String riskLevel;

    @Column(nullable = false)
    private double score;

    @Column(nullable = false, columnDefinition = "text")
    private String reason;

    @Column(name = "correlation_id", length = 128)
    private String correlationId;

    @Column(name = "simulation_id")
    private UUID simulationId;

    @Column(name = "tool_name", length = 100)
    private String toolName;

    /** Extrait du contenu analyse. DOIT etre masque avant stockage : jamais le contenu brut. */
    @Column(columnDefinition = "text")
    private String excerpt;

    protected Event() {
        // requis par JPA
    }

    public Event(GuardModule module, String attackType, Decision decision, String riskLevel, double score, String reason) {
        this.module = module;
        this.attackType = attackType;
        this.decision = decision;
        this.riskLevel = riskLevel;
        this.score = score;
        this.reason = reason;
    }

    public UUID getId() {
        return id;
    }

    public Instant getOccurredAt() {
        return occurredAt;
    }

    public GuardModule getModule() {
        return module;
    }

    public String getAttackType() {
        return attackType;
    }

    public Decision getDecision() {
        return decision;
    }

    public String getRiskLevel() {
        return riskLevel;
    }

    public double getScore() {
        return score;
    }

    public String getReason() {
        return reason;
    }

    public String getCorrelationId() {
        return correlationId;
    }

    public void setCorrelationId(String correlationId) {
        this.correlationId = correlationId;
    }

    public UUID getSimulationId() {
        return simulationId;
    }

    public void setSimulationId(UUID simulationId) {
        this.simulationId = simulationId;
    }

    public String getToolName() {
        return toolName;
    }

    public void setToolName(String toolName) {
        this.toolName = toolName;
    }

    public String getExcerpt() {
        return excerpt;
    }

    public void setExcerpt(String maskedExcerpt) {
        this.excerpt = maskedExcerpt;
    }
}
