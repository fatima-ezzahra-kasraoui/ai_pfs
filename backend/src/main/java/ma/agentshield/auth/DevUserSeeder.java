package ma.agentshield.auth;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.context.annotation.Profile;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Component;

/**
 * Cree un compte par role (analyst, approver, admin) UNIQUEMENT en profil {@code dev}, et seulement si
 * {@code DEV_SEED_PASSWORD} est defini. Aucun mot de passe n'est ecrit dans le code ni dans les journaux.
 */
@Component
@Profile("dev")
public class DevUserSeeder implements ApplicationRunner {

    private static final Logger log = LoggerFactory.getLogger(DevUserSeeder.class);

    private final UserAccountRepository users;
    private final PasswordEncoder encoder;
    private final String seedValue;

    public DevUserSeeder(UserAccountRepository users, PasswordEncoder encoder,
            @Value("${agentshield.dev-seed.password:}") String seedValue) {
        this.users = users;
        this.encoder = encoder;
        this.seedValue = seedValue;
    }

    @Override
    public void run(ApplicationArguments args) {
        if (seedValue == null || seedValue.isBlank()) {
            log.warn("Comptes de developpement non crees : definir la variable DEV_SEED_PASSWORD.");
            return;
        }
        for (Role role : Role.values()) {
            String username = role.name().toLowerCase();
            if (!users.existsByUsername(username)) {
                users.save(new UserAccount(username, encoder.encode(seedValue), role, username + "@exemple.test"));
            }
        }
        log.info("Comptes de developpement disponibles : analyst, approver, admin.");
    }
}
