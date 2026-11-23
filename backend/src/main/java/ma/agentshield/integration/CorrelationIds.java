package ma.agentshield.integration;

import java.util.UUID;

/** Identifiant de correlation : suit une requete du backend au service IA, puis aux evenements. */
public final class CorrelationIds {

    private CorrelationIds() {
    }

    public static String newId() {
        return UUID.randomUUID().toString();
    }
}
