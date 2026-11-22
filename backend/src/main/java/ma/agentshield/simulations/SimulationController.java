package ma.agentshield.simulations;

import jakarta.validation.Valid;
import java.util.UUID;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

@RestController
@RequestMapping("/api/simulations")
public class SimulationController {

    private final SimulationService service;
    private final SimulationRunner runner;

    public SimulationController(SimulationService service, SimulationRunner runner) {
        this.service = service;
        this.runner = runner;
    }

    /** Roles : ANALYST, ADMIN (contrat). Repond 202 immediatement ; l'execution continue en arriere-plan. */
    @PostMapping("/run")
    @PreAuthorize("hasAnyRole('ANALYST', 'ADMIN')")
    public ResponseEntity<SimulationAccepted> run(@Valid @RequestBody RunSimulationRequest body,
            Authentication authentication) {
        UUID id = service.create(body.scenarioId(), authentication.getName());
        runner.execute(id);
        return ResponseEntity.status(HttpStatus.ACCEPTED).body(new SimulationAccepted(id.toString(), SimulationStatus.SUBMITTED));
    }

    /** Roles : ANALYST, APPROVER, ADMIN. Un identifiant invalide ou inconnu donne 404. */
    @GetMapping("/{id}")
    public SimulationView get(@PathVariable String id) {
        UUID uuid;
        try {
            uuid = UUID.fromString(id);
        } catch (IllegalArgumentException e) {
            throw notFound();
        }
        return service.find(uuid).orElseThrow(SimulationController::notFound);
    }

    private static ResponseStatusException notFound() {
        return new ResponseStatusException(HttpStatus.NOT_FOUND, "Ressource introuvable.");
    }
}
