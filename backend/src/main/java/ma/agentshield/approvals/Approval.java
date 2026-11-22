package ma.agentshield.approvals;

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

/** Demande de validation humaine d'une action sensible (decision CONFIRM). */
@Entity
@Table(name = "approvals")
public class Approval {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    private UUID id;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false, length = 10)
    private ApprovalStatus status = ApprovalStatus.PENDING;

    @Column(name = "tool_name", nullable = false, length = 100)
    private String toolName;

    /** Parametres de l'appel d'outil ; masques a l'affichage selon le role. */
    @Column(name = "parameters_json", columnDefinition = "text")
    private String parametersJson;

    /** SHA-256 des parametres exacts : une approbation ne vaut que pour ces parametres. */
    @Column(name = "parameters_hash", nullable = false, length = 64)
    private String parametersHash;

    @Column(name = "risk_level", nullable = false, length = 10)
    private String riskLevel;

    @Column(nullable = false, columnDefinition = "text")
    private String reason;

    @Column(name = "simulation_id")
    private UUID simulationId;

    @Column(name = "event_id")
    private UUID eventId;

    @Column(name = "created_at", nullable = false, updatable = false)
    private Instant createdAt = Instant.now();

    @Column(name = "expires_at", nullable = false)
    private Instant expiresAt;

    @Column(name = "decided_by")
    private UUID decidedBy;

    @Column(name = "decided_at")
    private Instant decidedAt;

    @Column(name = "decision_comment", length = 500)
    private String decisionComment;

    protected Approval() {
        // requis par JPA
    }

    public Approval(String toolName, String parametersHash, String riskLevel, String reason, Instant expiresAt) {
        this.toolName = toolName;
        this.parametersHash = parametersHash;
        this.riskLevel = riskLevel;
        this.reason = reason;
        this.expiresAt = expiresAt;
    }

    public UUID getId() {
        return id;
    }

    public ApprovalStatus getStatus() {
        return status;
    }

    public void setStatus(ApprovalStatus status) {
        this.status = status;
    }

    public String getToolName() {
        return toolName;
    }

    public String getParametersJson() {
        return parametersJson;
    }

    public void setParametersJson(String parametersJson) {
        this.parametersJson = parametersJson;
    }

    public String getParametersHash() {
        return parametersHash;
    }

    public String getRiskLevel() {
        return riskLevel;
    }

    public String getReason() {
        return reason;
    }

    public UUID getSimulationId() {
        return simulationId;
    }

    public void setSimulationId(UUID simulationId) {
        this.simulationId = simulationId;
    }

    public UUID getEventId() {
        return eventId;
    }

    public void setEventId(UUID eventId) {
        this.eventId = eventId;
    }

    public Instant getCreatedAt() {
        return createdAt;
    }

    public Instant getExpiresAt() {
        return expiresAt;
    }

    public UUID getDecidedBy() {
        return decidedBy;
    }

    public void setDecidedBy(UUID decidedBy) {
        this.decidedBy = decidedBy;
    }

    public Instant getDecidedAt() {
        return decidedAt;
    }

    public void setDecidedAt(Instant decidedAt) {
        this.decidedAt = decidedAt;
    }

    public String getDecisionComment() {
        return decisionComment;
    }

    public void setDecisionComment(String decisionComment) {
        this.decisionComment = decisionComment;
    }
}
