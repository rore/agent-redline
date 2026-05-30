# spring-archunit — scaffold

What bootstrap generates and how. Each section maps to one artifact.

## 1. ArchUnit dependency

Add the JUnit 5 module to the build if absent. Pin to a known stable version.

**Gradle (Kotlin DSL):**
```kotlin
testImplementation("com.tngtech.archunit:archunit-junit5:1.3.0")
```

**Gradle (Groovy DSL):**
```groovy
testImplementation 'com.tngtech.archunit:archunit-junit5:1.3.0'
```

**Maven:**
```xml
<dependency>
    <groupId>com.tngtech.archunit</groupId>
    <artifactId>archunit-junit5</artifactId>
    <version>1.3.0</version>
    <scope>test</scope>
</dependency>
```

## 2. Architecture test class

Generate one `@ArchTest` method per `boundaries[]` entry in the policy. Test method name = boundary rule `id` (kebab-case → snake_case).

Substitute the actual base package and the actual layer package names from inspection. The example below uses placeholders (`domain`, `application`, `adapter`, `controller`); a repo using `core` / `infra` / `web` needs correspondingly different `resideInAPackage` arguments.

```java
// src/test/java/<base-package>/architecture/DependencyArchitectureTest.java

package <base-package>.architecture;

import com.tngtech.archunit.core.importer.ImportOption;
import com.tngtech.archunit.junit.AnalyzeClasses;
import com.tngtech.archunit.junit.ArchTest;
import com.tngtech.archunit.lang.ArchRule;

import static com.tngtech.archunit.lang.syntax.ArchRuleDefinition.noClasses;

@AnalyzeClasses(
    packages = "<base-package>",
    importOptions = ImportOption.DoNotIncludeTests.class
)
class DependencyArchitectureTest {

    @ArchTest
    static final ArchRule domain_must_not_depend_on_adapters =
        noClasses()
            .that().resideInAPackage("..domain..")
            .should().dependOnClassesThat()
            .resideInAnyPackage("..adapter..");

    @ArchTest
    static final ArchRule application_must_not_depend_on_persistence_adapters =
        noClasses()
            .that().resideInAPackage("..application..")
            .should().dependOnClassesThat()
            .resideInAnyPackage("..adapter..persistence..");

    @ArchTest
    static final ArchRule controllers_must_not_access_repositories_directly =
        noClasses()
            .that().resideInAPackage("..controller..")
            .should().dependOnClassesThat()
            .resideInAnyPackage("..repository..", "..adapter..persistence..");
}
```

## 3. Test report output

ArchUnit produces JUnit XML through Gradle's default test reporting. Verify nothing has disabled it. Default location: `build/test-results/test/`. If the project writes elsewhere, update `outputPath` in the policy's adapter config.

## 4. CI snippet

Add to the CI proposal:

```yaml
boundary:
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-java@v4
      with:
        distribution: temurin
        java-version: '21'                     # match the repo's Java version
    - run: ./gradlew test --tests '*ArchitectureTest'
```

For Maven: replace the `run:` line with `mvn -B test -Dtest='*ArchitectureTest'`.

## 5. Baseline for retrofit cases

Run `./gradlew test --tests '*ArchitectureTest'` during Phase 1 inspection. If it fails on `main`, the rules will need the baseline pattern (capture existing violations, fail CI for new ones only). See [docs/CI_INTEGRATION.md](https://github.com/rore/agent-redline/blob/main/docs/CI_INTEGRATION.md) for the pattern; flag the affected rules in the CI proposal.

## 6. OpenAPI generation (optional)

If the repo has an OpenAPI generation plugin (e.g., `org.springdoc.openapi-gradle-plugin`), the API-diff job in the CI proposal runs `./gradlew generateOpenApi` against base and head, then diffs.

If no plugin is configured, the policy uses `api.type: openapi-spec-file` (committed spec, path-diffed) or `api.type: none`. Don't auto-add a plugin; recommend it in the CI proposal if it would be useful.
