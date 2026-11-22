package ma.agentshield.support;

import java.util.UUID;

/** Mots de passe de test generes a l'execution : aucun secret en clair dans le depot (scan de secrets de la CI). */
public final class TestCredentials {

    private TestCredentials() {
    }

    public static String random() {
        return "pw-" + UUID.randomUUID();
    }
}
