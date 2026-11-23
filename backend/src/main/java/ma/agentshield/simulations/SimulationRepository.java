package ma.agentshield.simulations;

import java.util.UUID;
import org.springframework.data.jpa.repository.JpaRepository;

public interface SimulationRepository extends JpaRepository<Simulation, UUID> {
}
