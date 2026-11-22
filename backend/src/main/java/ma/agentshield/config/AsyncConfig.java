package ma.agentshield.config;

import org.springframework.context.annotation.Configuration;
import org.springframework.scheduling.annotation.EnableAsync;

/** Active {@code @Async} : l'execution d'une simulation ne bloque pas la requete HTTP (reponse 202). */
@Configuration
@EnableAsync
public class AsyncConfig {
}
