package ma.agentshield.integration;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.MediaType;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientException;

/**
 * Client du service IA (FastAPI). Chaque appel porte la cle de service ({@code X-AI-Service-Key}) et un
 * correlationId, avec un timeout de connexion et de lecture. Toute erreur devient une {@link AiServiceException}
 * generique : l'appelant decide (statut FAILED, decision BLOCK...), le backend ne laisse jamais passer une action
 * parce que le service IA est tombe.
 *
 * <p>Jamais de contenu utilisateur ni de cle dans les journaux : seulement chemin, correlationId et type d'erreur.
 */
@Component
public class AiServiceClient {

    static final String KEY_HEADER = "X-AI-Service-Key";
    static final String CORRELATION_HEADER = "X-Correlation-Id";

    private static final Logger log = LoggerFactory.getLogger(AiServiceClient.class);

    private final RestClient client;

    public AiServiceClient(RestClient.Builder builder, AiServiceProperties properties) {
        SimpleClientHttpRequestFactory factory = new SimpleClientHttpRequestFactory();
        factory.setConnectTimeout(properties.timeoutMs());
        factory.setReadTimeout(properties.timeoutMs());
        this.client = builder
                .baseUrl(properties.baseUrl())
                .requestFactory(factory)
                .defaultHeader(KEY_HEADER, properties.serviceKey())
                .build();
    }

    /** Execute un guard (A, B ou D) sur un texte et renvoie son verdict. */
    public Verdict analyze(String module, String text, String correlationId) {
        String id = correlationId != null ? correlationId : CorrelationIds.newId();
        return post("/internal/security/analyze", new AnalyzeRequest(module, text, "user_input", id), Verdict.class, id);
    }

    /** Fait executer un scenario par l'agent (sans ou avec protection). */
    public AgentRunResponse runAgent(AgentRunRequest request, String correlationId) {
        String id = correlationId != null ? correlationId : CorrelationIds.newId();
        return post("/internal/agent/run", request, AgentRunResponse.class, id);
    }

    private <T> T post(String path, Object body, Class<T> responseType, String correlationId) {
        try {
            T result = client.post()
                    .uri(path)
                    .contentType(MediaType.APPLICATION_JSON)
                    .header(CORRELATION_HEADER, correlationId)
                    .body(body)
                    .retrieve()
                    .body(responseType);
            if (result == null) {
                throw new AiServiceException(new IllegalStateException("reponse vide"));
            }
            return result;
        } catch (RestClientException e) {
            // Timeout, connexion refusee, statut 4xx/5xx ou JSON illisible.
            log.warn("Appel au service IA en echec path={} correlationId={} erreur={}", path, correlationId,
                    e.getClass().getSimpleName());
            throw new AiServiceException(e);
        }
    }
}
