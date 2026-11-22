package ma.agentshield;

import ma.agentshield.support.PostgresTestConfig;
import org.springframework.boot.SpringApplication;

/**
 * Lance l'application en local AVEC un PostgreSQL Testcontainers (Docker requis), sans rien configurer :
 * c'est le moyen le plus simple de demarrer le backend depuis l'IDE (clic droit sur main -> Run).
 * La base est jetable : elle disparait a l'arret.
 */
public class TestAgentShieldApplication {

    public static void main(String[] args) {
        SpringApplication.from(AgentShieldApplication::main).with(PostgresTestConfig.class).run(args);
    }
}
