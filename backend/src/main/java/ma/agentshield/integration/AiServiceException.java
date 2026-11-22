package ma.agentshield.integration;

/**
 * Le service IA est indisponible ou a repondu de facon inexploitable (timeout, connexion refusee, 4xx/5xx, JSON illisible).
 * Le message est GENERIQUE : il peut etre affiche tel quel (statut FAILED) sans reveler de detail interne.
 * Le detail technique est dans la cause et dans les journaux serveur uniquement.
 */
public class AiServiceException extends RuntimeException {

    public static final String GENERIC_MESSAGE = "Service IA indisponible.";

    public AiServiceException(Throwable cause) {
        super(GENERIC_MESSAGE, cause);
    }
}
