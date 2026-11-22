package ma.agentshield.auth;

/** Identite renvoyee au frontend (contrat : SessionUser). Jamais de hash ni de mot de passe. */
public record SessionUser(String username, Role role, String email) {
}
