package ma.agentshield.auth;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.UUID;
import ma.agentshield.support.PostgresTestConfig;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.context.annotation.Import;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;

/** En profil dev, avec DEV_SEED_PASSWORD, un compte par role est cree, mot de passe hache. */
@SpringBootTest
@Import(PostgresTestConfig.class)
@ActiveProfiles("dev")
class DevUserSeederTest {

    private static final String SEED_VALUE = "seed-" + UUID.randomUUID();

    @DynamicPropertySource
    static void seed(DynamicPropertyRegistry registry) {
        registry.add("agentshield.dev-seed.password", () -> SEED_VALUE);
    }

    @Autowired
    private UserAccountRepository users;

    @Autowired
    private PasswordEncoder encoder;

    @Test
    void createsOneAccountPerRoleWithHashedPasswords() {
        assertThat(users.count()).isEqualTo(3);
        for (Role role : Role.values()) {
            UserAccount account = users.findByUsername(role.name().toLowerCase()).orElseThrow();
            assertThat(account.getRole()).isEqualTo(role);
            assertThat(account.getPasswordHash()).startsWith("$2").isNotEqualTo(SEED_VALUE);
            assertThat(encoder.matches(SEED_VALUE, account.getPasswordHash())).isTrue();
        }
    }
}
