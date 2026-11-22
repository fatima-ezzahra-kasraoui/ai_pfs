package ma.agentshield.integration;

import org.springframework.boot.context.properties.ConfigurationProperties;

/**
 * Configuration du service IA (variables d'environnement AI_SERVICE_URL / AI_SERVICE_KEY, voir application.yml).
 * La cle de service n'est jamais journalisee.
 */
@ConfigurationProperties(prefix = "agentshield.ai-service")
public record AiServiceProperties(String baseUrl, String serviceKey, int timeoutMs) {
}
