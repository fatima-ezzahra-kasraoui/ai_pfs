package ma.agentshield.simulations;

import com.fasterxml.jackson.databind.ObjectMapper;
import java.time.Instant;
import java.util.List;
import java.util.UUID;
import ma.agentshield.integration.AgentRunRequest;
import ma.agentshield.integration.AgentRunResponse;
import ma.agentshield.integration.AiServiceClient;
import ma.agentshield.integration.AiServiceException;
import ma.agentshield.integration.CorrelationIds;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Component;

/**
 * Execute une simulation en arriere-plan : le scenario est joue SANS puis AVEC protection par le service IA.
 * Statuts : SUBMITTED -> RUNNING -> COMPLETED, ou FAILED si le service IA est indisponible (message generique).
 * AS-S2-025 ajoutera la persistance des evenements et l'etat AWAITING_APPROVAL.
 */
@Component
public class SimulationRunner {

    private static final Logger log = LoggerFactory.getLogger(SimulationRunner.class);

    private final SimulationRepository simulations;
    private final AiServiceClient aiClient;
    private final ScenarioCatalog catalog;
    private final ObjectMapper mapper;

    public SimulationRunner(SimulationRepository simulations, AiServiceClient aiClient, ScenarioCatalog catalog,
            ObjectMapper mapper) {
        this.catalog = catalog;
        this.simulations = simulations;
        this.aiClient = aiClient;
        this.mapper = mapper;
    }

    @Async
    public void execute(UUID simulationId) {
        Simulation sim = simulations.findById(simulationId).orElse(null);
        if (sim == null) {
            return;
        }
        sim.setStatus(SimulationStatus.RUNNING);
        sim = simulations.save(sim);
        try {
            SimulationRunView unprotected = run(sim.getScenarioId(), "unprotected");
            SimulationRunView protectedRun = run(sim.getScenarioId(), "protected");
            sim.setResultJson(mapper.writeValueAsString(new SimulationResult(unprotected, protectedRun)));
            sim.setStatus(SimulationStatus.COMPLETED);
        } catch (AiServiceException e) {
            sim.setStatus(SimulationStatus.FAILED);
            sim.setError(AiServiceException.GENERIC_MESSAGE);
        } catch (Exception e) {
            log.error("Echec inattendu de la simulation id={}", simulationId, e);
            sim.setStatus(SimulationStatus.FAILED);
            sim.setError("Erreur interne.");
        }
        sim.setCompletedAt(Instant.now());
        simulations.save(sim);
    }

    private SimulationRunView run(String scenarioId, String mode) {
        ScenarioCatalog.Scenario scenario = catalog.find(scenarioId).orElseThrow(() -> new IllegalStateException("scenario inconnu"));
        AgentRunResponse response = aiClient.runAgent(
                AgentRunRequest.of(scenarioId, scenario.message(), scenario.fixture(), mode), CorrelationIds.newId());
        List<AgentRunResponse.AgentEvent> events = response.events() == null ? List.of() : response.events();
        List<SimulationRunView.StepView> steps = events.stream()
                .map(e -> new SimulationRunView.StepView(e.stage(), "DONE", e.module(), e.decision(), e.score(),
                        e.reason(), e.latencyMs()))
                .toList();
        return new SimulationRunView(mode, steps, response.finalDecision(), response.attackSucceeded(), null);
    }
}
