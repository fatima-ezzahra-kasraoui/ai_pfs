package ma.agentshield.config;

/**
 * Format d'erreur JSON commun a toute l'API : jamais de trace interne.
 */
public record ApiError(int status, String code, String message) {
}
