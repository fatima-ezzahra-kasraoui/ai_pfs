package ma.agentshield.simulations;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.util.Optional;
import java.util.UUID;
import ma.agentshield.auth.UserAccount;
import ma.agentshield.auth.UserAccountRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;

@Service
public class SimulationService {

    private static final Logger log = LoggerFactory.getLogger(SimulationService.class);

    private final SimulationRepository simulations;
    private final UserAccountRepository users;
    private final ScenarioCatalog catalog;
    private final ObjectMapper mapper;

    public SimulationService(SimulationRepository simulations, UserAccountRepository users, ScenarioCatalog catalog,
            ObjectMapper mapper) {
        this.simulations = simulations;
        this.users = users;
        this.catalog = catalog;
        this.mapper = mapper;
    }

    /** Enregistre une simulation au statut SUBMITTED. Scenario inconnu : 400. */
    @Transactional
    public UUID create(String scenarioId, String username) {
        if (!catalog.isKnown(scenarioId)) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Scenario inconnu.");
        }
        UUID createdBy = users.findByUsername(username).map(UserAccount::getId).orElse(null);
        return simulations.save(new Simulation(scenarioId, createdBy)).getId();
    }

    @Transactional(readOnly = true)
    public Optional<SimulationView> find(UUID id) {
        return simulations.findById(id).map(this::toView);
    }

    private SimulationView toView(Simulation sim) {
        SimulationResult result = parse(sim);
        return new SimulationView(
                sim.getId().toString(),
                sim.getScenarioId(),
                sim.getStatus(),
                sim.getCreatedAt(),
                sim.getCompletedAt(),
                sim.getError(),
                result == null ? null : result.unprotected(),
                result == null ? null : result.protectedRun());
    }

    private SimulationResult parse(Simulation sim) {
        if (sim.getResultJson() == null) {
            return null;
        }
        try {
            return mapper.readValue(sim.getResultJson(), SimulationResult.class);
        } catch (JsonProcessingException e) {
            log.error("Resultat de simulation illisible id={}", sim.getId());
            return null;
        }
    }
}
